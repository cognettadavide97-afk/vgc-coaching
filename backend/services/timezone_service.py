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
# funzione viene chiamata dai router admin.py/booking.py, non dai model.

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
