# Vedi backend/schemas/users.py per la spiegazione generale degli schemi
# Pydantic e del pattern Create/Response.

from pydantic import BaseModel
from datetime import datetime
from typing import Literal

TipoPacchetto = Literal["intro", "team", "tour"]


class PackageCreate(BaseModel):
    user_id: int
    tipo: TipoPacchetto
    # Nota una cosa che NON c'è qui: nessun campo "prezzo" o "sessioni" —
    # esattamente come per BookingCreate (vedi backend/schemas/booking.py),
    # questi valori vengono presi dal catalogo fisso lato server
    # (backend/services/package_service.py), mai dal client.


class PackageResponse(BaseModel):
    id: int
    user_id: int
    tipo: str
    sessioni_totali: int
    sessioni_usate: int
    durata_sessione_ore: int
    prezzo_cents: int
    created_at: datetime

    class Config:
        from_attributes = True
