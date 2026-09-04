"""Job periodici in background.

È l'unico punto in cui il codice viene eseguito senza una richiesta HTTP:
APScheduler li esegue su un thread separato, in parallelo al server.

Otto job: promemoria pre-sessione, richieste di recensione, sincronizzazione
del calendario, generazione notturna degli slot, controllo delle credenziali
Gmail, data retention, pulizia degli slot obsoleti e backup del database.

Ogni funzione apre e chiude la propria sessione di database: non essendo
dentro una richiesta, non può usare la dependency di FastAPI.
"""

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

GMAIL_HEALTHCHECK_INTERVAL_HOURS = float(os.getenv("GMAIL_HEALTHCHECK_INTERVAL_HOURS", "24"))
# Esito dell'ultimo controllo, per notificare solo la transizione fra stato
# valido e non valido invece di ripetere l'avviso a ogni esecuzione.
# None finché il controllo non è mai stato eseguito in questo processo.
_ultimo_controllo_gmail_ok = None


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

            # Commit dentro il ciclo e non alla fine: se l'esecuzione si
            # interrompe, i promemoria già inviati non vengono ripetuti.
            prenotazione.reminder_sent = True
            db.commit()

        return len(prenotazioni)
    finally:
        db.close()


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


def controlla_credenziali_gmail():
    """Verifica le credenziali Gmail e notifica i cambi di stato.

    Non invia email. Avvisa solo alla transizione fra valido e non valido,
    in entrambe le direzioni, per non ripetere lo stesso alert a ogni
    esecuzione mentre il problema persiste.
    """
    global _ultimo_controllo_gmail_ok
    ok = verifica_credenziali_gmail()

    if not ok and _ultimo_controllo_gmail_ok is not False:
        invia_alert_sistema(
            "Refresh token Gmail scaduto o non valido",
            "L'invio email (conferme, promemoria, richieste recensione) è FERMO. "
            "Rifai l'autorizzazione con `python scripts/reauth_gmail.py`, poi "
            "aggiorna GMAIL_REFRESH_TOKEN su Railway (entrambi i servizi). "
            "La schermata di consenso è già \"In production\" dal 2026-09-04, "
            "quindi non è una scadenza periodica: guarda revoca dell'accesso o "
            "cambio dell'account mittente."
        )
    elif ok and _ultimo_controllo_gmail_ok is False:
        invia_alert_sistema(
            "Refresh token Gmail di nuovo valido",
            "L'invio email è ripreso a funzionare normalmente."
        )

    _ultimo_controllo_gmail_ok = ok
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
                "storico prenotazioni mantenuto in forma anonima)."
            )
        return anonimizzati
    finally:
        db.close()


def controlla_e_esegui_backup_database():
    """Esegue il backup del database e notifica solo in caso di fallimento.

    Un backup riuscito ogni giorno non merita una notifica quotidiana; uno
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


def avvia_scheduler():
    """Registra gli otto job e avvia lo scheduler.

    Restituisce l'istanza, che il chiamante deve conservare per poterla
    fermare alla chiusura dell'applicazione.
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
    scheduler.add_job(
        controlla_credenziali_gmail,
        "interval",
        hours=GMAIL_HEALTHCHECK_INTERVAL_HOURS,
        id="controlla_credenziali_gmail"
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
    # Prima del backup, così il dump non include slot che stanno per essere
    # eliminati.
    scheduler.add_job(
        pulisci_slot_obsoleti,
        "cron",
        hour=3,
        minute=2,
        id="pulisci_slot_obsoleti"
    )
    # Distanziato dagli altri job notturni: il dump legge l'intero
    # database.
    scheduler.add_job(
        controlla_e_esegui_backup_database,
        "cron",
        hour=4,
        minute=0,
        id="backup_database"
    )
    scheduler.start()
    return scheduler
