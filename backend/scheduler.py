"""Job periodici in background.

È l'unico punto in cui il codice viene eseguito senza una richiesta HTTP:
APScheduler li esegue su un thread separato, in parallelo al server.

Otto job: promemoria pre-sessione, richieste di recensione, sincronizzazione
del calendario, generazione notturna degli slot, controllo delle credenziali
Google, data retention, pulizia degli slot obsoleti e backup del database.

Sei girano ogni giorno; il controllo delle credenziali e il backup girano
una volta a settimana, la domenica alle 03:30 e alle 04:00 — in
quest'ordine, di proposito: vedi i commenti in `avvia_scheduler`.

Ogni funzione apre e chiude la propria sessione di database: non essendo
dentro una richiesta, non può usare la dependency di FastAPI.

Un ascoltatore unico, `sorveglia_job`, avvisa su Discord quando un job
inizia a fallire e quando torna a funzionare.
"""

import os
from datetime import timedelta
from typing import Callable, NamedTuple
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import contains_eager, joinedload
from backend.database import SessionLocal, engine
from backend.models.booking import Booking
from backend.models.slots import Slot
from backend.models.availability_rule import AvailabilityRule
from backend.services.email_service import invia_promemoria_cliente, invia_richiesta_recensione, verifica_credenziali_gmail
from backend.services.discord_service import invia_promemoria_discord, invia_alert_sistema
from backend.services.timezone_service import utc_to_rome, ora_utc_naive
from backend.services.calendar_service import sincronizza_slot_con_calendario, verifica_credenziali_calendario
from backend.services.availability_service import genera_slot_da_regola, elimina_slot_obsoleti
from backend.services.retention_service import anonimizza_clienti_inattivi, RETENTION_MONTHS
from backend.services.backup_service import esegui_backup_database, verifica_credenziali_drive

REMINDER_HOURS_BEFORE = float(os.getenv("REMINDER_HOURS_BEFORE", "24"))
CHECK_INTERVAL_MINUTES = int(os.getenv("REMINDER_CHECK_INTERVAL_MINUTES", "5"))

REVIEW_CHECK_INTERVAL_MINUTES = int(os.getenv("REVIEW_CHECK_INTERVAL_MINUTES", "60"))
# I link nelle email devono essere assoluti: un percorso relativo non
# funziona aperto da un client di posta. In mancanza di configurazione
# esplicita si ricade sulla prima origine consentita.
PUBLIC_BASE_URL = os.getenv(
    "PUBLIC_BASE_URL",
    os.getenv("FRONTEND_ORIGINS", "http://127.0.0.1:8000").split(",")[0]
).rstrip("/")

CALENDAR_SYNC_INTERVAL_MINUTES = int(os.getenv("CALENDAR_SYNC_INTERVAL_MINUTES", "60"))

# Esito dell'ultimo controllo di ciascuna credenziale, per notificare solo
# la transizione fra stato valido e non valido invece di ripetere l'avviso
# a ogni esecuzione. Una chiave assente significa "mai controllata in
# questo processo", che non è la stessa cosa di "controllata e rotta".
_ultimo_controllo_credenziali: dict[str, bool] = {}


class CredenzialeSorvegliata(NamedTuple):
    """Una credenziale esterna da controllare periodicamente.

    Tenere insieme sonda e testo dell'avviso evita il caso peggiore di un
    monitoraggio: un alert che segnala il guasto giusto ma suggerisce la
    cura sbagliata.
    """
    nome: str              # come compare nell'avviso su Discord
    sonda: Callable[[], bool]
    cosa_si_ferma: str     # cosa smette di funzionare, per chi legge l'alert
    come_si_ripara: str    # l'azione concreta, non "controlla la configurazione"


# Le tre integrazioni Google, in ordine di danno se cadono. Aggiungerne una
# quarta significa aggiungere una riga qui, non un job.
CREDENZIALI_SORVEGLIATE = (
    CredenzialeSorvegliata(
        nome="Gmail",
        sonda=verifica_credenziali_gmail,
        cosa_si_ferma="L'invio email (conferme, promemoria, richieste recensione) è FERMO.",
        come_si_ripara="Rifai l'autorizzazione con `python scripts/reauth_gmail.py`, "
                       "poi aggiorna GMAIL_REFRESH_TOKEN su Railway (entrambi i servizi).",
    ),
    CredenzialeSorvegliata(
        nome="Drive",
        sonda=verifica_credenziali_drive,
        cosa_si_ferma="Il backup del database su Google Drive NON può essere caricato: "
                      "alla prossima esecuzione il database resterà senza copia recente.",
        come_si_ripara="Rifai l'autorizzazione con `python scripts/reauth_drive.py`, "
                       "poi aggiorna DRIVE_REFRESH_TOKEN su Railway (entrambi i servizi).",
    ),
    CredenzialeSorvegliata(
        nome="Calendar",
        sonda=verifica_credenziali_calendario,
        cosa_si_ferma="La sincronizzazione con Google Calendar è ferma: gli impegni presi "
                      "fuori dall'app non bloccano più gli slot, e i nuovi eventi non vengono creati.",
        come_si_ripara="Controlla che il service account esista ancora su Google Cloud e che "
                       "GOOGLE_PRIVATE_KEY su Railway corrisponda a una chiave non revocata.",
    ),
)


def _query_prenotazioni_con_slot_e_utente(db):
    """Query di base condivisa dai due job che notificano i clienti.

    Restituisce la query senza filtri né esecuzione: le condizioni le
    aggiunge il chiamante. Il join sulla relationship (e non su `Slot`) è
    necessario perché due colonne puntano a slots, e l'eager loading evita
    due query aggiuntive per ogni prenotazione nel ciclo del chiamante.
    """
    return db.query(Booking).join(Booking.slot).options(
        contains_eager(Booking.slot),
        joinedload(Booking.user)
    )


def controlla_e_invia_promemoria():
    """Invia i promemoria per le sessioni imminenti non ancora notificate.

    Restituisce il numero di prenotazioni elaborate.
    """
    db = SessionLocal()
    try:
        ora = ora_utc_naive()
        soglia = ora + timedelta(hours=REMINDER_HOURS_BEFORE)

        prenotazioni = _query_prenotazioni_con_slot_e_utente(db).filter(
            Booking.status == "confirmed",
            Booking.reminder_sent == False,
            Slot.start_time > ora,       # non ancora passato
            Slot.start_time <= soglia    # ma abbastanza vicino
        ).all()

        for prenotazione in prenotazioni:
            user = prenotazione.user
            slot = prenotazione.slot
            if not user or not slot:
                continue  # sicurezza: salta se per qualche motivo mancano i dati collegati

            slot_rome = utc_to_rome(slot.start_time)
            data_slot = slot_rome.strftime("%d/%m/%Y")
            ora_slot = slot_rome.strftime("%H:%M")

            inviato = invia_promemoria_cliente(
                email_cliente=user.email,
                nome_cliente=user.nome,
                data_slot=data_slot,
                ora_slot=ora_slot,
                durata=prenotazione.duration_hours,
                riferimento=f"prenotazione {prenotazione.id}"
            )
            # Email fallita: la prenotazione resta da notificare e il
            # prossimo giro ci riprova, fino all'inizio della sessione
            # (filtro qui sopra). Anche Discord aspetta l'email: partendo a
            # ogni tentativo, avviserebbe il coach ogni pochi minuti.
            if not inviato:
                continue

            invia_promemoria_discord(
                nome_cliente=user.nome,
                discord_tag=user.discord_tag,
                data_slot=data_slot,
                ora_slot=ora_slot
            )

            # Commit dentro il ciclo e non alla fine: se l'esecuzione si
            # interrompe, i promemoria già inviati non vengono ripetuti.
            prenotazione.reminder_sent = True
            db.commit()

        return len(prenotazioni)
    finally:
        db.close()


# Un invio fallito si riprova a ogni giro, ma solo per le sessioni recenti:
# un errore permanente (un indirizzo che non esiste) verrebbe altrimenti
# ritentato ogni ora per sempre. Oltre una settimana chiedere un parere
# sulla sessione non ha più senso.
GIORNI_TENTATIVI_RECENSIONE = 7


def controlla_e_invia_richieste_recensione():
    """Invia la richiesta di recensione per le sessioni già concluse.

    Restituisce il numero di email inviate.
    """
    db = SessionLocal()
    try:
        ora = ora_utc_naive()

        # Pre-filtro conservativo: nessuna sessione supera le 2 ore, quindi
        # una iniziata prima è certamente conclusa. Riduce le righe da
        # esaminare senza escluderne di valide; la verifica esatta sulla
        # durata effettiva avviene nel ciclo.
        candidate = _query_prenotazioni_con_slot_e_utente(db).filter(
            Booking.status == "confirmed",
            Booking.review_email_sent == False,
            Slot.start_time <= ora - timedelta(hours=2),
            Slot.start_time >= ora - timedelta(days=GIORNI_TENTATIVI_RECENSIONE)
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
            if not invia_richiesta_recensione(
                email_cliente=user.email, nome_cliente=user.nome, link_recensione=link,
                riferimento=f"prenotazione {prenotazione.id}"
            ):
                continue  # resta da inviare: il prossimo giro ci riprova

            prenotazione.review_email_sent = True
            db.commit()
            inviate += 1

        return inviate
    finally:
        db.close()


def controlla_e_sincronizza_calendario():
    """Sincronizza gli slot con il calendario Google.

    Stessa logica del pulsante manuale nel pannello: un impegno aggiunto
    sul calendario blocca gli slot corrispondenti senza intervento.
    """
    db = SessionLocal()
    try:
        return sincronizza_slot_con_calendario(db)
    finally:
        db.close()


def genera_slot_giornaliero():
    """Genera gli slot mancanti da tutte le regole di disponibilità attive.

    Restituisce il numero di slot creati. Gira ogni giorno e non una volta
    a settimana perché la generazione arriva a fine mese corrente: con una
    cadenza settimanale, l'inizio di un mese in un giorno diverso da quello
    del job lascerebbe scoperti alcuni giorni. L'idempotenza rende
    innocue le esecuzioni ripetute.
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
    """Elimina gli slot passati e mai prenotati.

    Restituisce il numero di slot rimossi. Nessuna notifica: una pulizia di
    routine che non trova nulla da fare non è un evento da segnalare.
    """
    db = SessionLocal()
    try:
        return elimina_slot_obsoleti(db)
    finally:
        db.close()


def controlla_credenziali():
    """Verifica le credenziali Google e notifica i cambi di stato.

    Un solo job per tutte e tre: si rompono allo stesso modo e si
    verificano allo stesso modo, e tenerle separate significherebbe tre
    copie della stessa logica di transizione da mantenere allineate.

    Avvisa solo alla **transizione** fra valido e non valido, in entrambe
    le direzioni. Senza questa condizione l'avviso si ripeterebbe a ogni
    esecuzione finché il problema persiste, e un avviso che arriva sempre
    si impara a ignorare — il che lo rende inutile proprio quando conta.

    Restituisce l'esito di ciascuna credenziale, per nome.
    """
    esiti = {}
    for credenziale in CREDENZIALI_SORVEGLIATE:
        esiti[credenziale.nome] = controlla_una_credenziale(credenziale)
    return esiti


def controlla_una_credenziale(credenziale: CredenzialeSorvegliata) -> bool:
    """Esegue una sonda e avvisa se lo stato è cambiato dall'ultima volta.

    Separata da `controlla_credenziali` perché è l'unità che ha senso
    provare da sola: prende la credenziale da controllare invece di
    leggerla da una lista globale.
    """
    ok = credenziale.sonda()
    precedente = _ultimo_controllo_credenziali.get(credenziale.nome)

    # `is not False` e non `!= False`: al primo giro dopo un riavvio il
    # valore è None, cioè "mai controllato", e un guasto già in corso deve
    # comunque produrre l'avviso invece di passare per "nessun cambiamento".
    if not ok and precedente is not False:
        invia_alert_sistema(
            f"Credenziali {credenziale.nome} non valide",
            f"{credenziale.cosa_si_ferma} "
            f"{credenziale.come_si_ripara} "
            "La schermata di consenso Google è \"In production\" dal 2026-09-04, "
            "quindi non è una scadenza periodica: guarda revoca dell'accesso, "
            "cambio dell'account o rotazione della chiave."
        )
    elif ok and precedente is False:
        invia_alert_sistema(
            f"Credenziali {credenziale.nome} di nuovo valide",
            f"{credenziale.nome} è tornato a funzionare normalmente."
        )

    _ultimo_controllo_credenziali[credenziale.nome] = ok
    return ok


def controlla_e_anonimizza_clienti_inattivi():
    """Anonimizza i clienti inattivi oltre la soglia di retention.

    Notifica solo quando almeno un cliente viene anonimizzato, e riporta
    unicamente il conteggio: inserire nomi o email nella notifica
    rimetterebbe in circolo proprio i dati appena rimossi.
    """
    db = SessionLocal()
    try:
        anonimizzati = anonimizza_clienti_inattivi(db)
        if anonimizzati:
            invia_alert_sistema(
                "Data retention: clienti anonimizzati",
                f"{anonimizzati} cliente/i inattivo/i da oltre {RETENTION_MONTHS} mesi "
                "sono stati anonimizzati automaticamente (nome/email/contatti Discord rimossi, "
                "note del coach cancellate e note di prenotazione svuotate, "
                "storico prenotazioni mantenuto in forma anonima)."
            )
        return anonimizzati
    finally:
        db.close()


def controlla_e_esegui_backup_database():
    """Esegue il backup del database e notifica solo in caso di fallimento.

    Un backup riuscito ogni settimana non merita una notifica quotidiana; uno
    che smette di funzionare è invece un guasto silenzioso, che senza
    avviso si scoprirebbe solo quando il backup serve davvero.
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


# ─── Sorveglianza dei job (voce 47) ───────────────────────────

# Un job in ritardo parte comunque, una volta sola, invece di essere
# saltato. Il default di APScheduler (misfire_grace_time=1) scarta in
# silenzio ogni esecuzione partita con più di un secondo di ritardo; None
# toglie il limite. È sicuro perché tutti gli otto job sono del tipo
# "controlla cosa manca e fallo": eseguirli tardi non fa danni. coalesce è
# già il default, scritto per renderlo visibile, ed è la condizione perché
# None sia sicuro: senza, dopo una sospensione del processo un job
# recupererebbe una dopo l'altra tutte le esecuzioni perse, invece di una.
# Gli orari non si spostano: cambia cosa succede a un ritardo, non quando
# il job è previsto.
#
# Serve anche a sorveglia_job: APScheduler può chiamare l'ascoltatore dal
# proprio thread principale, e un avviso Discord (fino a 5 s di timeout)
# ritarderebbe gli altri job oltre il secondo di tolleranza, facendoli
# saltare proprio mentre si segnala un guasto.
TOLLERANZA_RITARDI = {"misfire_grace_time": None, "coalesce": True}

# Esito dell'ultima esecuzione di ciascun job, per avvisare solo al cambio
# di stato, come per le credenziali e per lo stesso motivo: un job ogni
# cinque minuti che continua a fallire manderebbe 288 avvisi al giorno.
# Una chiave assente significa "nessuna esecuzione in questo processo".
_ultimo_esito_job: dict[str, bool] = {}

# Solo riuscita e fallimento. EVENT_JOB_MISSED (job saltato per ritardo)
# non può più accadere con TOLLERANZA_RITARDI. EVENT_JOB_MAX_INSTANCES
# (esecuzione saltata perché la precedente è ancora in corso) non si
# avvisa: per i job a intervallo è innocuo, perché il giro in corso fa già
# il lavoro, e quando un giro dura poco più del suo intervallo l'avviso
# alternerebbe "saltato" e "di nuovo funzionante" a ogni giro. Un job
# davvero bloccato finisce comunque in errore, perché ogni chiamata esterna
# ha un tempo massimo, e quell'errore arriva qui.
EVENTI_SORVEGLIATI = EVENT_JOB_EXECUTED | EVENT_JOB_ERROR


def sorveglia_job(evento):
    """Avvisa su Discord quando un job inizia a fallire e quando torna a funzionare.

    Un solo ascoltatore per tutti i job: è APScheduler ad annunciare l'esito
    di ogni esecuzione, quindi nessun job deve ricordarsi di segnalare i
    propri errori. Copre i sei job che non avevano un avviso; backup e
    credenziali catturano da sé i propri guasti e li segnalano con un
    messaggio più preciso, quindi qui arrivano come esecuzioni riuscite.

    L'avviso riporta solo il tipo dell'errore, non il testo: quello di un
    errore del database contiene i valori della query, e un'email finirebbe
    su Discord. Il dettaglio resta nei log, dove APScheduler scrive lo
    stack trace di ogni job fallito.
    """
    precedente = _ultimo_esito_job.get(evento.job_id)

    if evento.code == EVENT_JOB_EXECUTED:
        if precedente is False:
            invia_alert_sistema(
                f"Job {evento.job_id} di nuovo funzionante",
                "L'ultima esecuzione è andata a buon fine."
            )
        _ultimo_esito_job[evento.job_id] = True
        return

    # `is not False`, come in controlla_una_credenziale: dopo un riavvio lo
    # stato è None, e un guasto già in corso deve comunque produrre l'avviso.
    if precedente is not False:
        invia_alert_sistema(
            f"Job {evento.job_id} non riuscito",
            f"L'esecuzione è finita con un errore ({type(evento.exception).__name__}). "
            "Il dettaglio è nei log di Railway. Non arriveranno altri avvisi per "
            "questo job finché non torna a funzionare."
        )
    _ultimo_esito_job[evento.job_id] = False


def avvia_scheduler():
    """Registra gli otto job e l'ascoltatore che ne sorveglia l'esito, poi avvia lo scheduler.

    Restituisce l'istanza, che il chiamante deve conservare per poterla
    fermare alla chiusura dell'applicazione.
    """
    # Senza timezone, di proposito: vedi l'ATTENZIONE più sotto.
    scheduler = BackgroundScheduler(job_defaults=TOLLERANZA_RITARDI)
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
    # I job notturni usano trigger cron, non interval: contano gli orari e
    # non il tempo trascorso dall'avvio.
    #
    # ATTENZIONE: lo scheduler è costruito senza timezone esplicita, quindi
    # questi orari sono quelli locali del processo. In produzione il
    # processo gira in UTC, quindi le 03:00 corrispondono alle 04:00 o alle
    # 05:00 italiane a seconda dell'ora legale. Nessun impatto pratico —
    # restano ore a basso traffico — ma va tenuto presente leggendo i log.
    scheduler.add_job(
        genera_slot_giornaliero,
        "cron",
        hour=3,
        minute=0,
        id="genera_slot_giornaliero"
    )
    # Settimanale e non giornaliero: con la schermata di consenso "In
    # production" la scadenza periodica non esiste più, e restano solo
    # revoca e cambio account — eventi rari e quasi sempre volontari. Un
    # controllo a settimana è la precauzione proporzionata al rischio.
    #
    # Le 03:30 della domenica non sono un orario qualsiasi: sono mezz'ora
    # prima del backup. È l'unica collocazione che rende utile la sonda
    # Drive, perché avvisa PRIMA che la copia salti invece che dopo. Se un
    # giorno il backup si sposta, questo job va spostato con lui.
    scheduler.add_job(
        controlla_credenziali,
        "cron",
        day_of_week="sun",
        hour=3,
        minute=30,
        id="controlla_credenziali"
    )
    # Cadenza giornaliera: la soglia di retention è in mesi. Sfalsato di un
    # minuto per non sovrapporlo al job precedente.
    scheduler.add_job(
        controlla_e_anonimizza_clienti_inattivi,
        "cron",
        hour=3,
        minute=1,
        id="controlla_retention_clienti"
    )
    # Resta giornaliero: è una pulizia di routine, non una copia. Girando
    # comunque prima delle 04:00, la domenica precede il backup e il dump
    # non include slot che stanno per essere eliminati.
    scheduler.add_job(
        pulisci_slot_obsoleti,
        "cron",
        hour=3,
        minute=2,
        id="pulisci_slot_obsoleti"
    )
    # Settimanale: il volume di dati è basso e cambia poco, quindi sei
    # dump identici a settimana costerebbero spazio e attenzione senza
    # aggiungere protezione. La finestra di perdita massima passa da 24 ore
    # a 7 giorni — accettata consapevolmente, non subita.
    #
    # Distanziato dagli altri job notturni: il dump legge l'intero
    # database. Mezz'ora dopo il controllo delle credenziali, così un token
    # Drive morto viene segnalato prima che la copia salti.
    scheduler.add_job(
        controlla_e_esegui_backup_database,
        "cron",
        day_of_week="sun",
        hour=4,
        minute=0,
        id="backup_database"
    )
    scheduler.add_listener(sorveglia_job, EVENTI_SORVEGLIATI)
    scheduler.start()
    return scheduler
