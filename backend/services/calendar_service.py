# Questo file parla con le API di Google Calendar: crea/elimina eventi
# quando una prenotazione viene confermata/cancellata, e legge gli eventi
# esistenti per sapere se il calendario del coach ha già impegni che
# dovrebbero bloccare uno slot (tornei, stream...). Come email_service.py,
# ogni funzione che chiama Google avvolge la chiamata in un try/except: un
# problema con Google Calendar non deve mai impedire il resto dell'app di
# funzionare.

import os
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv
from backend.services.timezone_service import ROME_TZ

load_dotenv()

# Un "service account" è un account Google speciale pensato per essere
# usato da un PROGRAMMA (non da una persona che fa login a mano). Ha una
# sua email e una sua chiave privata, e per potervi accedere il calendario
# del coach deve essere condiviso esplicitamente con quest'email (istruzioni
# nel README). SCOPES dice quali permessi stiamo chiedendo — qui, accesso
# completo al calendario.
SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")
SERVICE_ACCOUNT_EMAIL = os.getenv("GOOGLE_SERVICE_ACCOUNT_EMAIL")
# La chiave privata, nel file .env, è scritta su una sola riga con "\n"
# letterali al posto degli a capo veri (è un vincolo del formato .env, che
# non gestisce bene il testo multi-riga). .replace("\\n", "\n") converte
# quei caratteri letterali "\" + "n" in un vero carattere di a-capo, così la
# chiave torna ad avere il formato che Google si aspetta.
PRIVATE_KEY = os.getenv("GOOGLE_PRIVATE_KEY", "").replace("\\n", "\n")

logger = logging.getLogger(__name__)


def get_calendar_service():
    """
    Crea e restituisce il client autenticato
    per le Google Calendar API.
    """
    # service_account.Credentials.from_service_account_info() costruisce le
    # credenziali a partire da un dizionario con la forma esatta che
    # Google si aspetta (lo stesso formato del file JSON che si scarica
    # dalla Google Cloud Console).
    credenziali = service_account.Credentials.from_service_account_info(
        {
            "type": "service_account",
            "client_email": SERVICE_ACCOUNT_EMAIL,
            "private_key": PRIVATE_KEY,
            "token_uri": "https://oauth2.googleapis.com/token",
        },
        scopes=SCOPES
    )
    # build("calendar", "v3", ...) crea il "client" vero e proprio: un
    # oggetto con dei metodi (come .events()) che corrispondono uno a uno
    # alle azioni disponibili nell'API di Google Calendar versione 3.
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
    """
    Crea un evento su Google Calendar quando una
    prenotazione viene confermata dall'admin.
    """
    try:
        service = get_calendar_service()

        # data_slot e ora_slot arrivano già come testo formattato (es.
        # "12/08/2026" e "18:00" — vedi utc_to_rome in timezone_service.py).
        # datetime.strptime(testo, formato) fa l'operazione INVERSA di
        # strftime: legge una stringa e la trasforma in un oggetto datetime
        # vero, secondo il formato indicato ("%d/%m/%Y %H:%M" = giorno/mese/
        # anno ora:minuti).
        dt_inizio = datetime.strptime(
            f"{data_slot} {ora_slot}", "%d/%m/%Y %H:%M"
        )
        dt_fine = dt_inizio + timedelta(hours=durata_ore)

        formato = "%Y-%m-%dT%H:%M:%S"

        # "evento" è un semplice dizionario Python con la struttura esatta
        # richiesta dall'API di Google Calendar (documentata sul loro sito):
        # non è una classe speciale, solo dati organizzati come Google si
        # aspetta di riceverli. Notare "timeZone": "Europe/Rome" dentro
        # start/end: qui NON serve convertire in UTC a mano come altrove nel
        # progetto, perché l'API di Google accetta un orario "locale" più
        # l'indicazione esplicita di quale fuso sia — è Google stesso a
        # fare la conversione internamente.
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

        # service.events().insert(...).execute() è il pattern tipico delle
        # librerie client di Google: ogni pezzo della catena costruisce la
        # richiesta (calendario giusto, dati dell'evento...), e solo
        # .execute() finale la manda davvero e aspetta la risposta.
        risultato = service.events().insert(
            calendarId=CALENDAR_ID,
            body=evento
        ).execute()

        logger.info(f"Evento creato: {risultato.get('htmlLink')}")
        # Restituiamo solo l'id dell'evento (non l'intero risultato): è
        # quello che viene salvato nel campo calendar_event_id di Booking,
        # per poter più avanti eliminare esattamente questo evento se la
        # prenotazione viene cancellata.
        return risultato.get("id")

    except Exception:
        logger.exception("Errore Google Calendar")
        # Se qualcosa va storto restituiamo None invece di far esplodere
        # tutta la richiesta di prenotazione: un problema con Google
        # Calendar non deve impedire allo studente di completare la
        # prenotazione — semplicemente, quella prenotazione non avrà un
        # evento associato sul calendario del coach.
        return None


def leggi_eventi_calendario(time_min: datetime, time_max: datetime):
    """
    Legge tutti gli eventi sul calendario del coach nell'intervallo indicato
    (usato per bloccare automaticamente gli slot che si sovrappongono a
    tornei, stream o altri impegni esterni). Gli eventi "tutto il giorno"
    vengono trattati come se occupassero l'intera giornata in ora italiana.
    Restituisce una lista di tuple (inizio_utc, fine_utc), entrambe naive.
    """
    try:
        service = get_calendar_service()

        # service.events().list(...) chiede a Google tutti gli eventi in un
        # certo periodo. singleEvents=True dice "se un evento è ricorrente
        # (es. 'ogni lunedì'), restituiscimi ogni singola occorrenza
        # separatamente" invece della regola di ricorrenza grezza — molto
        # più semplice da elaborare per noi.
        eventi = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=time_min.strftime("%Y-%m-%dT%H:%M:%SZ"),
            timeMax=time_max.strftime("%Y-%m-%dT%H:%M:%SZ"),
            singleEvents=True,
            orderBy="startTime"
        ).execute().get("items", [])
        # .get("items", []) legge la lista di eventi dalla risposta; se la
        # chiave "items" non ci fosse per qualche motivo, il default []
        # (lista vuota) evita un errore invece di far scoppiare il programma.

        intervalli = []
        for evento in eventi:
            start_info = evento.get("start", {})
            end_info = evento.get("end", {})

            # Google Calendar rappresenta un evento "con orario" (es. 18-19)
            # in modo diverso da un evento "tutto il giorno" (es. una
            # giornata di ferie): il primo ha la chiave "dateTime", il
            # secondo solo "date". Dobbiamo gestire entrambi i casi.
            if "dateTime" in start_info and "dateTime" in end_info:
                # datetime.fromisoformat() legge una stringa già in formato
                # standard ISO (quello che Google restituisce, con l'offset
                # del fuso incluso) e la trasforma in un datetime
                # "consapevole" del proprio fuso. .astimezone(timezone.utc)
                # lo converte in UTC, .replace(tzinfo=None) lo rende
                # "naive" — lo stesso schema già visto in altri file.
                dt_inizio = datetime.fromisoformat(start_info["dateTime"]).astimezone(timezone.utc).replace(tzinfo=None)
                dt_fine = datetime.fromisoformat(end_info["dateTime"]).astimezone(timezone.utc).replace(tzinfo=None)
            elif "date" in start_info and "date" in end_info:
                # Un evento "tutto il giorno" non ha un orario preciso:
                # decidiamo noi di trattarlo come "dalla mezzanotte alla
                # mezzanotte successiva, ora italiana", per bloccare
                # l'intera giornata.
                giorno_inizio = datetime.strptime(start_info["date"], "%Y-%m-%d").replace(tzinfo=ROME_TZ)
                giorno_fine = datetime.strptime(end_info["date"], "%Y-%m-%d").replace(tzinfo=ROME_TZ)
                dt_inizio = giorno_inizio.astimezone(timezone.utc).replace(tzinfo=None)
                dt_fine = giorno_fine.astimezone(timezone.utc).replace(tzinfo=None)
            else:
                continue  # formato inatteso: saltiamo questo evento invece di far fallire tutto

            intervalli.append((dt_inizio, dt_fine))

        return intervalli

    except Exception:
        logger.exception("Errore lettura calendario")
        return []  # in caso di errore, meglio "nessun evento trovato" che bloccare la sincronizzazione


def sincronizza_slot_con_calendario(db: Session) -> int:
    """
    Legge il calendario Google del coach e blocca (is_available=False,
    blocked_external=True) gli slot liberi che si sovrappongono a un
    evento esterno (torneo, stream, altro impegno). Estratta qui da
    backend/routers/admin.py per essere richiamabile sia dal bottone
    manuale in admin (POST /admin/slots/sync-calendario) sia dal job
    automatico periodico in backend/scheduler.py — stessa identica
    logica, un solo posto da mantenere.
    """
    # Import locale (non in cima al file) per evitare un import circolare:
    # backend.models.slots non serve alle altre funzioni di questo modulo,
    # e admin.py importa già da qui.
    from backend.models.slots import Slot

    ora = datetime.now(timezone.utc).replace(tzinfo=None)

    slot_liberi = db.query(Slot).filter(
        Slot.is_available == True,
        Slot.start_time >= ora
    ).all()

    if not slot_liberi:
        return 0

    fine_intervallo = max(
        s.start_time + timedelta(hours=s.duration_hours) for s in slot_liberi
    )
    eventi = leggi_eventi_calendario(ora, fine_intervallo)

    bloccati = 0
    for slot in slot_liberi:
        slot_inizio = slot.start_time
        slot_fine = slot.start_time + timedelta(hours=slot.duration_hours)
        for evento_inizio, evento_fine in eventi:
            if slot_inizio < evento_fine and evento_inizio < slot_fine:
                slot.is_available = False
                slot.blocked_external = True
                bloccati += 1
                break

    db.commit()
    return bloccati


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
        logger.info(f"Evento {event_id} eliminato dal calendario")
    except Exception:
        logger.exception("Errore eliminazione evento")
