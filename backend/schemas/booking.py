# Vedi backend/schemas/users.py per la spiegazione generale degli schemi
# Pydantic e del pattern Create/Response.

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal

# Literal è un tipo speciale di Python (dal modulo typing, non solo di
# Pydantic) che dice "questo valore può essere SOLO uno di questi testi
# esatti, nient'altro". A differenza di "str" (che accetterebbe qualunque
# stringa), Literal[...] fa sì che Pydantic rifiuti automaticamente
# qualunque servizio diverso da questi quattro — è un modo per avere
# nel codice Python l'equivalente di un "enum" senza dover creare una
# classe Enum a parte. Il valore effettivamente scelto arriva così già
# garantito valido a tutto il resto del programma.
ServiceType = Literal["vod_review", "team_building", "bo3_sparring", "mentality_prep"]


class BookingCreate(BaseModel):
    user_id: int
    slot_id: int
    duration_hours: int = 1
    service_type: ServiceType  # deve essere uno dei 4 valori sopra, altrimenti 422 automatico
    note_cliente: Optional[str] = None
    vod_link: Optional[str] = None
    replay_code: Optional[str] = None

    # Nota una cosa che NON c'è qui: nessun campo "price". Il prezzo non lo
    # decide mai il client — viene sempre calcolato dal server (vedi
    # TABELLA_PREZZI in backend/routers/booking.py) in base a duration_hours.
    # Se permettessimo al client di mandare direttamente il prezzo,
    # chiunque potrebbe modificare la richiesta HTTP con gli strumenti
    # sviluppatore del browser e prenotare a prezzo zero: il server non
    # deve MAI fidarsi di dati sensibili calcolabili in autonomia.


class BookingResponse(BaseModel):
    id: int
    user_id: int
    slot_id: int
    duration_hours: int
    price_cents: int
    service_type: str
    status: str
    note_cliente: Optional[str]
    note_admin: Optional[str]
    vod_link: Optional[str]
    replay_code: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
