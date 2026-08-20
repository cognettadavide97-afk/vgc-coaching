# Vedi backend/schemas/users.py per la spiegazione generale degli schemi
# Pydantic.

from pydantic import BaseModel, EmailStr
from typing import Optional


class ConsulenzaCreate(BaseModel):
    nome: str
    email: EmailStr
    discord_tag: Optional[str] = None
    messaggio: Optional[str] = None
