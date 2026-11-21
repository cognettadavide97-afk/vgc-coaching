"""Integrazione con Google Calendar.

In scrittura crea ed elimina l'evento associato a una prenotazione; in
lettura recupera gli impegni del coach, che il calcolo delle ore
prenotabili toglie dalla vendita (services/disponibilita_service.py).

In scrittura nessuna funzione propaga eccezioni: un'indisponibilità di
Google non deve impedire una prenotazione. In lettura sì, ed è voluto:
`leggi_eventi_calendario` solleva `CalendarioNonRaggiungibile`, perché un
guasto scambiato per "nessun impegno" metterebbe in vendita orari occupati.

Autenticazione tramite service account, con il calendario del coach
condiviso esplicitamente con la sua email.
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from google.oauth2 import service_account
from backend.services.google_oauth_service import verifica_credenziali_google
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
from backend.services.timezone_service import ROME_TZ

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")
SERVICE_ACCOUNT_EMAIL = os.getenv("GOOGLE_SERVICE_ACCOUNT_EMAIL")
# Il formato .env non gestisce valori multi-riga: la chiave privata è
# salvata con "\n" letterali, che vanno riconvertiti in a capo reali.
PRIVATE_KEY = os.getenv("GOOGLE_PRIVATE_KEY", "").replace("\\n", "\n")

logger = logging.getLogger(__name__)


class CalendarioNonRaggiungibile(Exception):
    """Google Calendar non ha risposto: gli impegni del coach sono ignoti.

    Esiste per non confondere il guasto con l'agenda vuota. Restituire []
    direbbe "nessun impegno", e chi decide quali ore vendere le aprirebbe
    tutte: nel dubbio si chiude (decisioni P1 e P9).
    """


def _credenziali_service_account():
    """Credenziali del service account, condivise dal client e dalla sonda."""
    return service_account.Credentials.from_service_account_info(
        {
            "type": "service_account",
            "client_email": SERVICE_ACCOUNT_EMAIL,
            "private_key": PRIVATE_KEY,
            "token_uri": "https://oauth2.googleapis.com/token",
        },
        scopes=SCOPES
    )


def get_calendar_service():
    """Costruisce il client autenticato per le API di Google Calendar."""
    return build("calendar", "v3", credentials=_credenziali_service_account())


def verifica_credenziali_calendario() -> bool:
    """Verifica che le credenziali del service account siano ancora valide.

    Qui la credenziale non è un refresh token ma una chiave privata, che
    non scade da sola: il guasto atteso è la revoca della chiave, la
    cancellazione del service account o una rotazione fatta senza
    aggiornare `GOOGLE_PRIVATE_KEY`. La prova resta la stessa, perché anche
    un service account ottiene l'access token scambiando le proprie
    credenziali.

    Serviva un controllo perché questa integrazione è la più silenziosa
    delle tre: per anni la sincronizzazione degli slot (rimossa nel pezzo
    4.6a) ha catturato ogni errore lasciandolo solo nei log. Oggi un guasto
    in lettura arriva a chi chiede le ore, con un 503 al sito e
    all'anteprima, ma se nessuno le chiede nessuno lo vede: la sonda
    settimanale è il segnale che arriva comunque al coach.

    Attenzione al limite: verifica l'identità, non il permesso. Un
    calendario che smettesse di essere condiviso con il service account
    darebbe credenziali valide e il sito comunque senza ore, perché la
    lettura degli impegni verrebbe rifiutata.
    """
    return verifica_credenziali_google("Calendar", _credenziali_service_account)


def crea_evento_calendario(
    nome_cliente: str,
    categoria: str,
    data_slot: str,
    ora_slot: str,
    durata_ore: int,
    riferimento: str
):
    """Crea l'evento associato a una prenotazione.

    Restituisce l'id dell'evento, da salvare su `Booking.calendar_event_id`
    per poterlo eliminare in caso di cancellazione, oppure None se la
    creazione fallisce: la prenotazione resta valida anche senza evento.

    `riferimento` ("prenotazione 42") va nei log al posto dell'email, come
    negli invii di email_service.py (voce 50), e nella descrizione
    dell'evento.

    L'evento contiene solo ciò che serve all'agenda (voce 39): il nome di
    battesimo, il numero della prenotazione, categoria e durata. Niente
    email, niente note e niente cognome, e la firma non li riceve nemmeno,
    così non si possono rimettere per sbaglio. Google Calendar non viene
    ripulito né dall'anonimizzazione dei 24 mesi né dalla cancellazione su
    richiesta: un dato copiato qui resterebbe per sempre. Contatti e note
    il coach li trova nel pannello e nel promemoria Discord del giorno prima.
    """
    try:
        service = get_calendar_service()

        # data_slot e ora_slot arrivano già formattati in ora italiana.
        dt_inizio = datetime.strptime(
            f"{data_slot} {ora_slot}", "%d/%m/%Y %H:%M"
        )
        dt_fine = dt_inizio + timedelta(hours=durata_ore)

        formato = "%Y-%m-%dT%H:%M:%S"

        # Solo il nome di battesimo, come nelle recensioni pubbliche
        # (routers/booking.py): al coach basta per riconoscere la sessione.
        # split() senza argomenti e il ripiego reggono anche un nome vuoto o
        # fatto di soli spazi, che lo schema non vieta.
        nome_di_battesimo = (nome_cliente.split() or [nome_cliente])[0]

        # L'API accetta un orario locale accompagnato dal fuso: qui, a
        # differenza del resto del progetto, non serve convertire in UTC.
        evento = {
            "summary": f"Coaching VGC — {nome_di_battesimo}",
            "description": (
                f"Riferimento: {riferimento}\n"
                f"Categoria: {categoria or 'non specificata'}\n"
                f"Durata: {durata_ore} ora{'e' if durata_ore > 1 else ''}\n"
                "Contatti e note: nel pannello e nel promemoria Discord."
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

        logger.info("Evento creato (%s): %s", riferimento, risultato.get("htmlLink"))
        return risultato.get("id")

    except Exception:
        logger.exception("Errore Google Calendar (%s)", riferimento)
        return None


def leggi_eventi_calendario(time_min: datetime, time_max: datetime):
    """Restituisce gli intervalli occupati nel periodo indicato.

    Lista di tuple (inizio_utc, fine_utc), entrambe naive. Se Google non
    risponde solleva `CalendarioNonRaggiungibile`: una lista vuota vorrebbe
    dire "nessun impegno", e il guasto non deve mai sembrarlo.
    """
    try:
        service = get_calendar_service()

        # singleEvents espande le ricorrenze in occorrenze singole, molto
        # più semplici da confrontare con le ore.
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
                # giornata italiana, così da toglierne tutte le ore.
                giorno_inizio = datetime.strptime(start_info["date"], "%Y-%m-%d").replace(tzinfo=ROME_TZ)
                giorno_fine = datetime.strptime(end_info["date"], "%Y-%m-%d").replace(tzinfo=ROME_TZ)
                dt_inizio = giorno_inizio.astimezone(timezone.utc).replace(tzinfo=None)
                dt_fine = giorno_fine.astimezone(timezone.utc).replace(tzinfo=None)
            else:
                continue  # formato inatteso: si salta l'evento, non l'intera sync

            intervalli.append((dt_inizio, dt_fine))

        return intervalli

    except Exception as errore:
        logger.exception("Errore lettura calendario")
        raise CalendarioNonRaggiungibile() from errore


def elimina_evento_calendario(event_id: str) -> bool:
    """Elimina l'evento associato a una prenotazione cancellata.

    Restituisce True quando l'evento non è più sul calendario, False quando
    la cancellazione non è riuscita. L'eccezione resta catturata come in
    tutto il modulo: cambia solo che l'esito diventa leggibile, perché chi
    chiama deve sapere se può dimenticare l'id dell'evento (vedi
    libera_slot_prenotazione in services/booking_service.py).
    """
    try:
        service = get_calendar_service()
        service.events().delete(
            calendarId=CALENDAR_ID,
            eventId=event_id
        ).execute()
        logger.info(f"Evento {event_id} eliminato dal calendario")
        return True
    except HttpError as errore:
        # 404 e 410 dicono che l'evento non c'è più: già cancellato a mano
        # dal coach, oppure id stantio. Non è un guasto, l'obiettivo è
        # raggiunto. Trattarlo come fallimento condannerebbe il chiamante a
        # conservare per sempre un id che non punta a niente, perché nessuno
        # ripasserà mai a riprovare.
        if errore.resp.status in (404, 410):
            logger.info(f"Evento {event_id} già assente dal calendario")
            return True
        logger.exception("Errore eliminazione evento")
        return False
    except Exception:
        logger.exception("Errore eliminazione evento")
        return False
