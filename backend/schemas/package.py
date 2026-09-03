"""Schemi Pydantic per i pacchetti di sessioni."""

from pydantic import BaseModel
from datetime import datetime
from typing import Literal

TipoPacchetto = Literal["intro", "team", "tour"]


class PackageCreate(BaseModel):
    """Dati accettati per assegnare un pacchetto a un cliente.

    Non include prezzo né numero di sessioni: sono presi dal catalogo lato
    server, così un client non può alterare le condizioni del pacchetto.
    """
    user_id: int
    tipo: TipoPacchetto


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
