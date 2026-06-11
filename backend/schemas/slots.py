from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class SlotCreate(BaseModel):
    start_time: datetime
    duration_hours: int = 1

class SlotResponse(BaseModel):
    id: int
    start_time: datetime
    duration_hours: int
    is_available: bool

    class Config:
        from_attributes = True