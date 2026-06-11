from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

class UserCreate(BaseModel):
    nome: str
    email: EmailStr
    telefono: Optional[str] = None
    showdown_username: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    nome: str
    email: str
    telefono: Optional[str]
    showdown_username: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True