# Vedi backend/schemas/users.py per la spiegazione generale degli schemi
# Pydantic.

from pydantic import BaseModel, EmailStr
from typing import Optional, Literal

TipoPacchetto = Literal["intro", "team", "tour"]


class PacchettoRichiestaCreate(BaseModel):
    nome: str
    email: EmailStr
    discord_tag: Optional[str] = None
    tipo: TipoPacchetto
    messaggio: Optional[str] = None
