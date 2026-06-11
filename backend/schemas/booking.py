from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class BookingCreate(BaseModel):
    user_id: int
    slot_id: int
    duration_hours: int = 1
    note_cliente: Optional[str] = None

class BookingResponse(BaseModel):
    id: int
    user_id: int
    slot_id: int
    duration_hours: int
    price_cents: int
    status: str
    note_cliente: Optional[str]
    note_admin: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True