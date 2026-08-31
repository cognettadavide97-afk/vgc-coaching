# File piccolo ma usato ovunque nel progetto: una singola funzione che
# risolve un problema molto comune (e molto fonte di bug) nelle app web —
# mostrare un orario nel fuso giusto.
#
# La convenzione scelta in questo progetto (vedi anche i commenti in
# backend/models/slots.py e backend/schemas/slots.py) è: tutto ciò che
# viene SALVATO nel database è sempre in UTC. Ma un umano (il coach) non
# vuole leggere "16:00 UTC" — vuole leggere "18:00", la sua ora locale. Il
# lavoro di conversione va fatto SOLO nel momento in cui un orario deve
# essere mostrato, mai mentre viaggia dentro il sistema — per questo questa
# funzione viene chiamata dai router del package admin/ e da booking.py, non dai model.

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Vedi il commento più dettagliato su ZoneInfo in backend/schemas/slots.py:
# è la libreria standard di Python per gestire i fusi orari "veri",
# comprese le regole di cambio ora legale.
ROME_TZ = ZoneInfo("Europe/Rome")


def utc_to_rome(dt: datetime) -> datetime:
    """Converte un datetime naive-UTC (come salvato nel DB) nell'ora locale di Roma, per la visualizzazione."""
    # Come nello schema SlotResponse, il valore che arriva da SQLAlchemy è
    # "naive" (senza fuso esplicito) — prima di poterlo convertire in
    # ora italiana, dobbiamo dirgli esplicitamente "sappi che sei UTC".
    # .replace(tzinfo=...) NON cambia i numeri dell'orario, attacca solo
    # l'etichetta del fuso.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    # .astimezone(ROME_TZ) invece SPOSTA davvero l'orario, calcolando la
    # differenza corretta (che cambia da 1 a 2 ore a seconda del periodo
    # dell'anno, grazie a ZoneInfo che conosce le regole dell'ora legale
    # italiana) e restituisce un nuovo datetime già "consapevole" di essere
    # in ora italiana.
    return dt.astimezone(ROME_TZ)


def formatta_data_ora_rome(dt: datetime) -> tuple[str, str]:
    """
    Converte un datetime naive-UTC in ora di Roma e lo formatta subito nelle
    due stringhe (data, ora) che quasi ogni endpoint admin mostra affiancate
    (dashboard, lista prenotazioni, lista slot, export CSV) — prima questa
    stessa coppia di .strftime() veniva ripetuta in ognuno di quei punti.
    """
    dt_rome = utc_to_rome(dt)
    return dt_rome.strftime("%d/%m/%Y"), dt_rome.strftime("%H:%M")


def ora_utc_naive() -> datetime:
    """
    "Adesso", nella stessa forma naive-UTC salvata nel DB — serve per
    confrontare l'ora attuale con Slot.start_time/Booking.created_at ecc.
    senza il mismatch aware/naive che darebbe un confronto diretto con
    datetime.now(). Ripetuta identica in una dozzina di punti del progetto
    prima di questa funzione condivisa.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def intervalli_si_sovrappongono(inizio1: datetime, fine1: datetime, inizio2: datetime, fine2: datetime) -> bool:
    """
    True se gli intervalli [inizio1, fine1) e [inizio2, fine2) si
    sovrappongono. Il modo standard per capire se due intervalli di tempo si
    sovrappongono è controllare "A inizia prima che B finisca, E B inizia
    prima che A finisca" — la stessa identica condizione serviva sia per
    controllare due Slot tra loro (availability_service.py) sia uno Slot
    contro un evento Google Calendar (calendar_service.py), prima ridefinita
    a mano in entrambi i punti.
    """
    return inizio1 < fine2 and inizio2 < fine1
