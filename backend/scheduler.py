# Questo file implementa i promemoria automatici pre-sessione. È l'unico
# punto del progetto dove il codice si esegue "da solo", senza che nessuna
# richiesta web lo attivi — per questo serve una libreria diversa da FastAPI:
# APScheduler, che sa eseguire una funzione ripetutamente, a intervalli
# regolari, in un "thread" separato che gira in parallelo al resto del
# programma (un thread è un filo di esecuzione indipendente: mentre FastAPI
# risponde alle richieste web, questo thread controlla i promemoria per
# conto suo, senza bloccare nulla).

import os
from datetime import timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import contains_eager, joinedload
from backend.database import SessionLocal, engine
from backend.models.booking import Booking
from backend.models.slots import Slot
from backend.models.availability_rule import AvailabilityRule
from backend.services.email_service import invia_promemoria_cliente, invia_richiesta_recensione, verifica_credenziali_gmail
from backend.services.discord_service import invia_promemoria_discord, invia_alert_sistema
from backend.services.timezone_service import utc_to_rome, ora_utc_naive
from backend.services.calendar_service import sincronizza_slot_con_calendario
from backend.services.availability_service import genera_slot_da_regola, elimina_slot_obsoleti
from backend.services.retention_service import anonimizza_clienti_inattivi, RETENTION_MONTHS
from backend.services.backup_service import esegui_backup_database

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

GMAIL_HEALTHCHECK_INTERVAL_HOURS = float(os.getenv("GMAIL_HEALTHCHECK_INTERVAL_HOURS", "24"))
# Ricorda l'esito dell'ultimo controllo, per mandare l'alert Discord solo
# al MOMENTO in cui le credenziali smettono di funzionare (transizione
# ok→rotto), non a ogni singolo controllo mentre restano rotte — altrimenti,
# con un controllo giornaliero, il coach riceverebbe lo stesso alert ogni
# giorno finché non risolve, invece di uno solo. None = non ancora
# controllato da quando il server è partito.
_ultimo_controllo_gmail_ok = None


def _query_prenotazioni_con_slot_e_utente(db):
    """
    Query di base condivisa da controlla_e_invia_promemoria e
    controlla_e_invia_richieste_recensione qui sotto: entrambe cercano
    prenotazioni filtrando su Slot.start_time e poi, nel ciclo, leggono
    prenotazione.user/prenotazione.slot — questa funzione fa solo il JOIN
    e l'eager-loading comuni (senza .filter() né .all()), lasciando a chi
    la chiama aggiungere le proprie condizioni.

    .join(Booking.slot) è necessario perché la condizione sulla data
    (Slot.start_time, aggiunta dal chiamante) riguarda la tabella slots,
    non bookings — bisogna "unire" le due tabelle per poterle confrontare
    nella stessa query, esattamente come faresti con una JOIN in SQL puro.
    Passiamo la relationship (Booking.slot) e non solo "Slot": da quando
    Booking ha due colonne che puntano a slots (slot_id e
    slot_id_secondario), ".join(Slot)" da solo non saprebbe più quale usare.

    .options(contains_eager(Booking.slot), joinedload(Booking.user)):
    senza queste due righe, chi cicla sul risultato farebbe DUE query in
    più per OGNI prenotazione (una per lo User, una per lo Slot) anche se
    lo Slot era già stato unito dal .join() sopra — un classico problema
    "N+1 query" (N prenotazioni = 1 query iniziale + N*2 query ripetute
    nel ciclo). contains_eager dice a SQLAlchemy "lo Slot lo hai già preso
    col JOIN qui sopra, riempi booking.slot con quello invece di andarlo a
    riprendere"; joinedload aggiunge un secondo JOIN (a users) nella
    STESSA query per riempire anche booking.user. Risultato: una singola
    query SQL per l'intero controllo, qualunque sia il numero di
    prenotazioni trovate.
    """
    return db.query(Booking).join(Booking.slot).options(
        contains_eager(Booking.slot),
        joinedload(Booking.user)
    )


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
        ora = ora_utc_naive()
        soglia = ora + timedelta(hours=REMINDER_HOURS_BEFORE)

        # Una query con più condizioni: SQLAlchemy le combina tutte con "AND".
        # Vedi _query_prenotazioni_con_slot_e_utente sopra per il JOIN e
        # l'eager-loading condivisi con controlla_e_invia_richieste_recensione.
        prenotazioni = _query_prenotazioni_con_slot_e_utente(db).filter(
            Booking.status == "confirmed",
            Booking.reminder_sent == False,
            Slot.start_time > ora,       # non ancora passato
            Slot.start_time <= soglia    # ma abbastanza vicino
        ).all()

        # Per ogni prenotazione trovata, mandiamo i due promemoria e
        # segniamo la prenotazione come "già avvisata", per non ripeterlo
        # al prossimo controllo (tra CHECK_INTERVAL_MINUTES minuti).
        for prenotazione in prenotazioni:
            user = prenotazione.user
            slot = prenotazione.slot
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
        ora = ora_utc_naive()

        # Pre-filtro largo lato database: nessuna sessione dura più di 2
        # ore (vedi TABELLA_PREZZI in backend/routers/booking.py), quindi
        # uno slot iniziato più di 2 ore fa è SEMPRE già concluso — questo
        # riduce le righe da controllare senza rischiare di escluderne una
        # che in realtà è già finita. Il controllo esatto (che tiene conto
        # della durata reale di ciascuna prenotazione) avviene poi in
        # Python riga per riga.
        candidate = _query_prenotazioni_con_slot_e_utente(db).filter(
            Booking.status == "confirmed",
            Booking.review_email_sent == False,
            Slot.start_time <= ora - timedelta(hours=2)
        ).all()

        inviate = 0
        for prenotazione in candidate:
            user = prenotazione.user
            slot = prenotazione.slot
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


def pulisci_slot_obsoleti():
    """
    Elimina gli slot passati mai prenotati (vedi elimina_slot_obsoleti in
    backend/services/availability_service.py) — senza questo job si
    accumulano per sempre nel database, invisibili al form pubblico ma
    sempre più numerosi nella lista slot del pannello admin. Nessun alert
    Discord: una pulizia di routine che trova 0 slot da eliminare (il caso
    più comune) non è un evento degno di nota, stesso principio già seguito
    dagli altri job silenziosi di questo file.
    """
    db = SessionLocal()
    try:
        return elimina_slot_obsoleti(db)
    finally:
        db.close()


def controlla_credenziali_gmail():
    """
    Controllo di salute periodico (non manda nessuna email): verifica che
    GMAIL_REFRESH_TOKEN sia ancora valido (vedi verifica_credenziali_gmail
    in backend/services/email_service.py per il perché può scadere) e, solo
    quando smette di funzionare, avvisa il coach su Discord — che a quel
    punto deve rifare l'autorizzazione con scripts/reauth_gmail.py e
    aggiornare la variabile d'ambiente su Railway.
    """
    global _ultimo_controllo_gmail_ok
    ok = verifica_credenziali_gmail()

    if not ok and _ultimo_controllo_gmail_ok is not False:
        invia_alert_sistema(
            "Refresh token Gmail scaduto o non valido",
            "L'invio email (conferme, promemoria, richieste recensione) è FERMO. "
            "Rifai l'autorizzazione con `python scripts/reauth_gmail.py`, poi "
            "aggiorna GMAIL_REFRESH_TOKEN su Railway. Vedi README.md, sezione "
            "\"Gmail API\", per evitare che si ripeta (schermata di consenso "
            "OAuth in stato \"In production\" invece di \"Testing\")."
        )
    elif ok and _ultimo_controllo_gmail_ok is False:
        invia_alert_sistema(
            "Refresh token Gmail di nuovo valido",
            "L'invio email è ripreso a funzionare normalmente."
        )

    _ultimo_controllo_gmail_ok = ok
    return ok


def controlla_e_anonimizza_clienti_inattivi():
    """
    Applica la data retention (vedi backend/services/retention_service.py):
    anonimizza i clienti inattivi da più di RETENTION_MONTHS mesi. Avvisa
    su Discord SOLO quando ne anonimizza almeno uno (stesso spirito di
    controlla_credenziali_gmail: un evento degno di nota, non un log
    silenzioso) — il messaggio riporta solo il conteggio, mai nomi o email,
    per non rimettere in un log/canale Discord proprio i dati che
    l'anonimizzazione doveva far sparire.
    """
    db = SessionLocal()
    try:
        anonimizzati = anonimizza_clienti_inattivi(db)
        if anonimizzati:
            invia_alert_sistema(
                "Data retention: clienti anonimizzati",
                f"{anonimizzati} cliente/i inattivo/i da oltre {RETENTION_MONTHS} mesi "
                "sono stati anonimizzati automaticamente (nome/email/contatti Discord rimossi, "
                "storico prenotazioni mantenuto in forma anonima)."
            )
        return anonimizzati
    finally:
        db.close()


def controlla_e_esegui_backup_database():
    """
    Genera un backup completo del database e lo carica su Google Drive
    (vedi backend/services/backup_service.py per il perché: il piano
    Railway attuale non include backup automatici). Avvisa su Discord SOLO
    in caso di FALLIMENTO — un backup riuscito ogni giorno non merita un
    messaggio quotidiano (stesso principio di controlla_credenziali_gmail),
    ma un backup che smette di funzionare è esattamente il tipo di problema
    silenzioso che si scopre troppo tardi, quando servirebbe davvero.
    """
    ok = esegui_backup_database(engine)
    if not ok:
        invia_alert_sistema(
            "Backup database fallito",
            "Il backup automatico su Google Drive non è riuscito. Controlla i log "
            "del server per il dettaglio dell'errore — finché non è risolto, il "
            "database di produzione non ha nessuna copia di sicurezza recente."
        )
    return ok


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
    scheduler.add_job(
        controlla_credenziali_gmail,
        "interval",
        hours=GMAIL_HEALTHCHECK_INTERVAL_HOURS,
        id="controlla_credenziali_gmail"
    )
    # cron, non interval: una volta al giorno basta e avanza per un
    # controllo di retention (la soglia è di MESI, non di minuti) — stesso
    # orario a basso traffico di genera_slot_giornaliero, un minuto dopo per
    # non farli partire nello stesso istante.
    scheduler.add_job(
        controlla_e_anonimizza_clienti_inattivi,
        "cron",
        hour=3,
        minute=1,
        id="controlla_retention_clienti"
    )
    # Un minuto dopo la retention, stesso orario a basso traffico: elimina
    # gli slot obsoleti PRIMA del backup delle 4:00, così il dump notturno
    # non si porta dietro slot che stiamo per cancellare comunque.
    scheduler.add_job(
        pulisci_slot_obsoleti,
        "cron",
        hour=3,
        minute=2,
        id="pulisci_slot_obsoleti"
    )
    # Un'ora dopo gli altri job notturni: il dump legge l'intero database,
    # meglio non farlo nello stesso istante in cui girano anche retention e
    # generazione slot.
    scheduler.add_job(
        controlla_e_esegui_backup_database,
        "cron",
        hour=4,
        minute=0,
        id="backup_database"
    )
    scheduler.start()
    return scheduler
