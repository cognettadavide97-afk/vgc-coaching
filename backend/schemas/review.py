# Vedi backend/schemas/users.py per la spiegazione generale degli schemi
# Pydantic.

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class ReviewCreate(BaseModel):
    token: str  # deve combaciare con Booking.review_token, vedi backend/routers/booking.py
    # Field(ge=1, le=5) dice a Pydantic di rifiutare automaticamente un voto
    # fuori dal range 1-5 (ge = "greater or equal", le = "less or equal"),
    # senza bisogno di un "if" scritto a mano.
    voto: int = Field(ge=1, le=5)
    commento: Optional[str] = None


class ReviewResponse(BaseModel):
    id: int
    booking_id: int
    voto: int
    commento: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
