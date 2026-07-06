import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")
SERVICE_ACCOUNT_EMAIL = os.getenv("GOOGLE_SERVICE_ACCOUNT_EMAIL")
PRIVATE_KEY = os.getenv("GOOGLE_PRIVATE_KEY", "").replace("\\n", "\n")


def get_calendar_service():
    """
    Crea e restituisce il client autenticato
    per le Google Calendar API.
    """
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
    showdown_username: str,
    data_slot: str,
    ora_slot: str,
    durata_ore: int,
    note_cliente: str = None
):
    """
    Crea un evento su Google Calendar quando una
    prenotazione viene confermata dall'admin.
    """
    try:
        service = get_calendar_service()

        # costruisce data e ora di inizio e fine
        # data_slot è "dd/mm/yyyy", ora_slot è "HH:MM"
        from datetime import datetime, timedelta
        dt_inizio = datetime.strptime(
            f"{data_slot} {ora_slot}", "%d/%m/%Y %H:%M"
        )
        dt_fine = dt_inizio + timedelta(hours=durata_ore)

        # formatta nel formato richiesto da Google Calendar
        formato = "%Y-%m-%dT%H:%M:%S"

        evento = {
            "summary": f"Coaching VGC — {nome_cliente}",
            "description": (
                f"Cliente: {nome_cliente}\n"
                f"Email: {email_cliente}\n"
                f"Showdown: {showdown_username or 'non specificato'}\n"
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
            "attendees": [
                {"email": email_cliente}
            ],
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
            body=evento,
            sendUpdates="all"
        ).execute()

        print(f"Evento creato: {risultato.get('htmlLink')}")
        return risultato.get("id")

    except Exception as e:
        print(f"Errore Google Calendar: {e}")
        return None


def elimina_evento_calendario(event_id: str):
    """
    Elimina un evento dal calendario quando
    una prenotazione viene cancellata dall'admin.
    """
    try:
        service = get_calendar_service()
        service.events().delete(
            calendarId=CALENDAR_ID,
            eventId=event_id
        ).execute()
        print(f"Evento {event_id} eliminato dal calendario")
    except Exception as e:
        print(f"Errore eliminazione evento: {e}")