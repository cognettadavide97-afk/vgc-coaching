"""Integrazione con Google Calendar.

In scrittura crea ed elimina l'evento associato a una prenotazione; in
lettura recupera gli impegni esistenti per bloccare gli slot sovrapposti.

Nessuna funzione propaga eccezioni: un'indisponibilità di Google non deve
impedire una prenotazione né interrompere la sincronizzazione.

Autenticazione tramite service account, con il calendario del coach
condiviso esplicitamente con la sua email.
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv
from backend.services.timezone_service import ROME_TZ, ora_utc_naive, intervalli_si_sovrappongono

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")
SERVICE_ACCOUNT_EMAIL = os.getenv("GOOGLE_SERVICE_ACCOUNT_EMAIL")
# Il formato .env non gestisce valori multi-riga: la chiave privata è
# salvata con "\n" letterali, che vanno riconvertiti in a capo reali.
PRIVATE_KEY = os.getenv("GOOGLE_PRIVATE_KEY", "").replace("\\n", "\n")

logger = logging.getLogger(__name__)


def get_calendar_service():
    """Costruisce il client autenticato per le API di Google Calendar."""
    credenziali = service_account.Credentials.from_service_account_info(
        {
            "type": "service_account",
            "client_email": SERVICE_ACCOUNT_EMAIL,
            "private_key": PRIVATE_KEY,
            "token_uri": "https://oauth2.googleapis.com/token",
        },
        scopes=SCOPES
    )
    return build("calendar", "v3", credentials=credenziali)


def crea_evento_calendario(
    nome_cliente: str,
    email_cliente: str,
    categoria: str,
    data_slot: str,
    ora_slot: str,
    durata_ore: int,
    note_cliente: str = None
):
    """Crea l'evento associato a una prenotazione.

    Restituisce l'id dell'evento, da salvare su `Booking.calendar_event_id`
    per poterlo eliminare in caso di cancellazione, oppure None se la
    creazione fallisce: la prenotazione resta valida anche senza evento.
    """
    try:
        service = get_calendar_service()

        # data_slot e ora_slot arrivano già formattati in ora italiana.
        dt_inizio = datetime.strptime(
            f"{data_slot} {ora_slot}", "%d/%m/%Y %H:%M"
        )
        dt_fine = dt_inizio + timedelta(hours=durata_ore)

        formato = "%Y-%m-%dT%H:%M:%S"

        # L'API accetta un orario locale accompagnato dal fuso: qui, a
        # differenza del resto del progetto, non serve convertire in UTC.
        evento = {
            "summary": f"Coaching VGC — {nome_cliente}",
            "description": (
                f"Cliente: {nome_cliente}\n"
                f"Email: {email_cliente}\n"
                f"Categoria: {categoria or 'non specificata'}\n"
                f"Durata: {durata_ore} ora{'e' if durata_ore > 1 else ''}\n"
                f"Note: {note_cliente or 'nessuna'}"
            ),
            "start": {
                "dateTime": dt_inizio.strftime(formato),
                "timeZone": "Europe/Rome"
            },
            "end": {
                "dateTime": dt_fine.strftime(formato),
                "timeZone": "Europe/Rome"
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email", "minutes": 60},
                    {"method": "popup", "minutes": 30}
                ]
            }
        }

        risultato = service.events().insert(
            calendarId=CALENDAR_ID,
            body=evento
        ).execute()

        logger.info(f"Evento creato: {risultato.get('htmlLink')}")
        return risultato.get("id")

    except Exception:
        logger.exception("Errore Google Calendar")
        return None


def leggi_eventi_calendario(time_min: datetime, time_max: datetime):
    """Restituisce gli intervalli occupati nel periodo indicato.

    Lista di tuple (inizio_utc, fine_utc), entrambe naive. In caso di
    errore restituisce una lista vuota: la sincronizzazione non blocca
    nulla anziché fallire.
    """
    try:
        service = get_calendar_service()

        # singleEvents espande le ricorrenze in occorrenze singole, molto
        # più semplici da confrontare con gli slot.
        eventi = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=time_min.strftime("%Y-%m-%dT%H:%M:%SZ"),
            timeMax=time_max.strftime("%Y-%m-%dT%H:%M:%SZ"),
            singleEvents=True,
            orderBy="startTime"
        ).execute().get("items", [])

        intervalli = []
        for evento in eventi:
            start_info = evento.get("start", {})
            end_info = evento.get("end", {})

            # Gli eventi con orario espongono "dateTime", quelli di
            # un'intera giornata solo "date": vanno gestiti separatamente.
            if "dateTime" in start_info and "dateTime" in end_info:
                dt_inizio = datetime.fromisoformat(start_info["dateTime"]).astimezone(timezone.utc).replace(tzinfo=None)
                dt_fine = datetime.fromisoformat(end_info["dateTime"]).astimezone(timezone.utc).replace(tzinfo=None)
            elif "date" in start_info and "date" in end_info:
                # Un evento "tutto il giorno" viene trattato come l'intera
                # giornata italiana, così da bloccarne tutti gli slot.
                giorno_inizio = datetime.strptime(start_info["date"], "%Y-%m-%d").replace(tzinfo=ROME_TZ)
                giorno_fine = datetime.strptime(end_info["date"], "%Y-%m-%d").replace(tzinfo=ROME_TZ)
                dt_inizio = giorno_inizio.astimezone(timezone.utc).replace(tzinfo=None)
                dt_fine = giorno_fine.astimezone(timezone.utc).replace(tzinfo=None)
            else:
                continue  # formato inatteso: si salta l'evento, non l'intera sync

            intervalli.append((dt_inizio, dt_fine))

        return intervalli

    except Exception:
        logger.exception("Errore lettura calendario")
        return []


def sincronizza_slot_con_calendario(db: Session) -> int:
    """Blocca gli slot liberi sovrapposti a impegni esterni sul calendario.

    Restituisce il numero di slot bloccati. Condivisa fra il pulsante
    manuale del pannello e il job periodico, che devono comportarsi allo
    stesso modo.
    """
    # Import locale per evitare un ciclo: il router che importa da qui
    # importa a sua volta i model.
    from backend.models.slots import Slot

    ora = ora_utc_naive()

    slot_liberi = db.query(Slot).filter(
        Slot.is_available == True,
        Slot.start_time >= ora
    ).all()

    if not slot_liberi:
        return 0

    # Una sola lettura del calendario per l'intero periodo coperto dagli
    # slot, invece di una richiesta per slot.
    fine_intervallo = max(
        s.start_time + timedelta(hours=s.duration_hours) for s in slot_liberi
    )
    eventi = leggi_eventi_calendario(ora, fine_intervallo)

    bloccati = 0
    for slot in slot_liberi:
        slot_inizio = slot.start_time
        slot_fine = slot.start_time + timedelta(hours=slot.duration_hours)
        for evento_inizio, evento_fine in eventi:
            if intervalli_si_sovrappongono(slot_inizio, slot_fine, evento_inizio, evento_fine):
                slot.is_available = False
                slot.blocked_external = True
                bloccati += 1
                break

    db.commit()
    return bloccati


def elimina_evento_calendario(event_id: str):
    """Elimina l'evento associato a una prenotazione cancellata."""
    try:
        service = get_calendar_service()
        service.events().delete(
            calendarId=CALENDAR_ID,
            eventId=event_id
        ).execute()
        logger.info(f"Evento {event_id} eliminato dal calendario")
    except Exception:
        logger.exception("Errore eliminazione evento")
