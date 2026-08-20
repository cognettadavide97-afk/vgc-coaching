# Questo file implementa i promemoria automatici pre-sessione. È l'unico
# punto del progetto dove il codice si esegue "da solo", senza che nessuna
# richiesta web lo attivi — per questo serve una libreria diversa da FastAPI:
# APScheduler, che sa eseguire una funzione ripetutamente, a intervalli
# regolari, in un "thread" separato che gira in parallelo al resto del
# programma (un thread è un filo di esecuzione indipendente: mentre FastAPI
# risponde alle richieste web, questo thread controlla i promemoria per
# conto suo, senza bloccare nulla).

import os
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from backend.database import SessionLocal
from backend.models.booking import Booking
from backend.models.slots import Slot
from backend.models.users import User
from backend.models.availability_rule import AvailabilityRule
from backend.services.email_service import invia_promemoria_cliente, invia_richiesta_recensione
from backend.services.discord_service import invia_promemoria_discord
from backend.services.timezone_service import utc_to_rome
from backend.services.calendar_service import sincronizza_slot_con_calendario
from backend.services.availability_service import genera_slot_da_regola

# Entrambi i valori sono letti da variabili d'ambiente con un default se
# mancano (os.getenv(nome, default)) — così restano configurabili senza
# toccare il codice, ma funzionano comunque "out of the box" in sviluppo.
REMINDER_HOURS_BEFORE = float(os.getenv("REMINDER_HOURS_BEFORE", "24"))
CHECK_INTERVAL_MINUTES = int(os.getenv("REMINDER_CHECK_INTERVAL_MINUTES", "5"))

REVIEW_CHECK_INTERVAL_MINUTES = int(os.getenv("REVIEW_CHECK_INTERVAL_MINUTES", "60"))
# Dominio pubblico usato per costruire link assoluti nelle email (il link
# di recensione deve funzionare quando aperto da un client email, non ha
# senso relativo). Se non impostata esplicitamente, usiamo la prima
# origine configurata in FRONTEND_ORIGINS (vedi backend/main.py) — in
# produzione è comunque il dominio Railway vero.
PUBLIC_BASE_URL = os.getenv(
    "PUBLIC_BASE_URL",
    os.getenv("FRONTEND_ORIGINS", "http://127.0.0.1:8000").split(",")[0]
).rstrip("/")

CALENDAR_SYNC_INTERVAL_MINUTES = int(os.getenv("CALENDAR_SYNC_INTERVAL_MINUTES", "60"))


def controlla_e_invia_promemoria():
    """
    Questa è la funzione che APScheduler richiama ogni CHECK_INTERVAL_MINUTES
    minuti. Non riceve nessun parametro da FastAPI (niente Depends(get_db)
    qui!) perché non gira dentro una richiesta web — per questo deve aprirsi
    e chiudersi la propria connessione al database da sola, con lo stesso
    SessionLocal usato altrove ma chiamato direttamente.

    La logica, in breve: "trova tutte le prenotazioni confermate il cui
    orario è abbastanza vicino da meritare un promemoria, e per cui non ne
    ho già mandato uno".
    """
    db = SessionLocal()
    try:
        # datetime.now(timezone.utc) dà l'ora attuale "consapevole" del fuso
        # (sa di essere UTC). .replace(tzinfo=None) la rende "naive" (senza
        # fuso attaccato) perché nel database gli orari sono salvati così —
        # per poterli confrontare, devono essere nello stesso "formato".
        # Questo pattern lo ritrovi identico in molti altri file del backend.
        ora = datetime.now(timezone.utc).replace(tzinfo=None)
        soglia = ora + timedelta(hours=REMINDER_HOURS_BEFORE)

        # Una query con più condizioni: SQLAlchemy le combina tutte con "AND".
        # .join(Slot) è necessario perché la condizione sulla data (Slot.start_time)
        # riguarda la tabella slots, non bookings — bisogna "unire" le due
        # tabelle per poterle confrontare nella stessa query, esattamente
        # come faresti con una JOIN in SQL puro.
        prenotazioni = db.query(Booking).join(Slot).filter(
            Booking.status == "confirmed",
            Booking.reminder_sent == False,
            Slot.start_time > ora,       # non ancora passato
            Slot.start_time <= soglia    # ma abbastanza vicino
        ).all()

        # Per ogni prenotazione trovata, mandiamo i due promemoria e
        # segniamo la prenotazione come "già avvisata", per non ripeterlo
        # al prossimo controllo (tra CHECK_INTERVAL_MINUTES minuti).
        for prenotazione in prenotazioni:
            user = db.query(User).filter(User.id == prenotazione.user_id).first()
            slot = db.query(Slot).filter(Slot.id == prenotazione.slot_id).first()
            if not user or not slot:
                continue  # sicurezza: salta se per qualche motivo mancano i dati collegati

            # utc_to_rome converte l'orario (salvato in UTC) in ora italiana,
            # solo per mostrarlo in modo leggibile nell'email/messaggio.
            slot_rome = utc_to_rome(slot.start_time)
            data_slot = slot_rome.strftime("%d/%m/%Y")
            ora_slot = slot_rome.strftime("%H:%M")

            invia_promemoria_cliente(
                email_cliente=user.email,
                nome_cliente=user.nome,
                data_slot=data_slot,
                ora_slot=ora_slot,
                durata=prenotazione.duration_hours
            )

            invia_promemoria_discord(
                nome_cliente=user.nome,
                discord_tag=user.discord_tag,
                data_slot=data_slot,
                ora_slot=ora_slot
            )

            # Marchiamo la prenotazione come avvisata e salviamo subito
            # (db.commit() dentro il ciclo, non solo alla fine): così, se il
            # programma si interrompesse a metà, i promemoria già inviati
            # non verrebbero rimandati al controllo successivo.
            prenotazione.reminder_sent = True
            db.commit()

        return len(prenotazioni)
    finally:
        # Come get_db() in database.py, anche qui la connessione va sempre
        # chiusa, che tutto sia andato bene o no.
        db.close()


def controlla_e_invia_richieste_recensione():
    """
    Gemella di controlla_e_invia_promemoria sopra, stessa struttura
    (SessionLocal proprio, try/finally), ma cerca prenotazioni la cui
    sessione è già FINITA (non "in arrivo") e per cui non è ancora stata
    mandata la richiesta di recensione.
    """
    db = SessionLocal()
    try:
        ora = datetime.now(timezone.utc).replace(tzinfo=None)

        # Pre-filtro largo lato database: nessuna sessione dura più di 2
        # ore (vedi TABELLA_PREZZI in backend/routers/booking.py), quindi
        # uno slot iniziato più di 2 ore fa è SEMPRE già concluso — questo
        # riduce le righe da controllare senza rischiare di escluderne una
        # che in realtà è già finita. Il controllo esatto (che tiene conto
        # della durata reale di ciascuna prenotazione) avviene poi in
        # Python riga per riga.
        candidate = db.query(Booking).join(Slot).filter(
            Booking.status == "confirmed",
            Booking.review_email_sent == False,
            Slot.start_time <= ora - timedelta(hours=2)
        ).all()

        inviate = 0
        for prenotazione in candidate:
            user = db.query(User).filter(User.id == prenotazione.user_id).first()
            slot = db.query(Slot).filter(Slot.id == prenotazione.slot_id).first()
            if not user or not slot or not prenotazione.review_token:
                continue

            fine_sessione = slot.start_time + timedelta(hours=prenotazione.duration_hours)
            if fine_sessione > ora:
                continue  # sessione non ancora conclusa nonostante il pre-filtro largo

            link = f"{PUBLIC_BASE_URL}/static/recensione.html?booking_id={prenotazione.id}&token={prenotazione.review_token}"
            invia_richiesta_recensione(email_cliente=user.email, nome_cliente=user.nome, link_recensione=link)

            prenotazione.review_email_sent = True
            db.commit()
            inviate += 1

        return inviate
    finally:
        db.close()


def controlla_e_sincronizza_calendario():
    """
    Richiama a intervalli regolari la stessa logica del bottone manuale
    "Sync calendario" del pannello admin (sincronizza_slot_con_calendario in
    backend/services/calendar_service.py), così un impegno esterno aggiunto
    dal coach sul suo Google Calendar blocca gli slot corrispondenti da
    solo, senza dover ricordarsi di premere il bottone.
    """
    db = SessionLocal()
    try:
        return sincronizza_slot_con_calendario(db)
    finally:
        db.close()


def genera_slot_giornaliero():
    """
    Estende automaticamente la finestra di slot generati da ogni regola di
    disponibilità ricorrente ATTIVA (AvailabilityRule.attiva — prima volta
    che questo campo viene davvero usato per filtrare, vedi il commento nel
    model). genera_slot_da_regola (backend/services/availability_service.py)
    genera sempre fino alla fine del MESE CORRENTE ed è idempotente (salta
    gli slot già esistenti) — per questo può girare ogni giorno invece che
    una volta a settimana: appena scatta la mezzanotte del primo giorno di
    un mese nuovo, la finestra "fine mese" si allarga da sola e i suoi
    slot vengono generati entro 24 ore, invece di dover aspettare il
    prossimo lunedì (con un cron settimanale, un 1° del mese "sbagliato"
    — es. di martedì — avrebbe lasciato scoperti diversi giorni).
    """
    db = SessionLocal()
    try:
        regole_attive = db.query(AvailabilityRule).filter(AvailabilityRule.attiva == True).all()
        totale_creati = 0
        for regola in regole_attive:
            totale_creati += genera_slot_da_regola(regola, db)
        return totale_creati
    finally:
        db.close()


def avvia_scheduler():
    """
    Crea e avvia lo scheduler in background. BackgroundScheduler è la
    versione di APScheduler pensata per girare "dentro" un programma già
    attivo (come il nostro server web), su un thread separato — a differenza
    di un cron job del sistema operativo, che sarebbe un programma esterno.

    add_job(...) registra "cosa" eseguire (controlla_e_invia_promemoria),
    "quando" ("interval" = a intervalli regolari) e "ogni quanto"
    (minutes=CHECK_INTERVAL_MINUTES). Da quando scheduler.start() viene
    chiamato (in main.py, all'avvio dell'app), la funzione gira da sola,
    per sempre, finché il programma resta acceso.
    """
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        controlla_e_invia_promemoria,
        "interval",
        minutes=CHECK_INTERVAL_MINUTES,
        id="controlla_promemoria"
    )
    scheduler.add_job(
        controlla_e_invia_richieste_recensione,
        "interval",
        minutes=REVIEW_CHECK_INTERVAL_MINUTES,
        id="controlla_recensioni"
    )
    scheduler.add_job(
        controlla_e_sincronizza_calendario,
        "interval",
        minutes=CALENDAR_SYNC_INTERVAL_MINUTES,
        id="sincronizza_calendario"
    )
    # trigger "cron" invece di "interval": non "ogni tot minuti da quando è
    # partito il programma", ma un orario preciso e ricorrente — ogni notte
    # alle 03:00 (niente "day_of_week": senza quel filtro un trigger cron
    # gira tutti i giorni), un momento a basso traffico in cui non ha
    # importanza se il server è momentaneamente più lento a generare gli slot.
    scheduler.add_job(
        genera_slot_giornaliero,
        "cron",
        hour=3,
        minute=0,
        id="genera_slot_giornaliero"
    )
    scheduler.start()
    return scheduler
