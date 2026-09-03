"""Schemi Pydantic per le recensioni."""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class ReviewCreate(BaseModel):
    token: str  # confrontato con Booking.review_token per autorizzare l'invio
    voto: int = Field(ge=1, le=5)
    commento: Optional[str] = None


class ReviewResponse(BaseModel):
    id: int
    booking_id: int
    voto: int
    commento: Optional[str]
    approvata: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ReviewApprovazione(BaseModel):
    approvata: bool


class ReviewPubblica(BaseModel):
    """Recensione come appare nella vetrina pubblica.

    Esclude ogni riferimento interno (booking_id, contatti). `nome_cliente`
    è composto dall'endpoint con il solo nome di battesimo e non esiste
    come colonna sul model.
    """
    id: int
    voto: int
    commento: Optional[str]
    nome_cliente: str
    created_at: datetime

    class Config:
        from_attributes = True
