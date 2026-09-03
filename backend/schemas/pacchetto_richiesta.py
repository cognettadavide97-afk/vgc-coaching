"""Schema Pydantic per la richiesta di attivazione di un pacchetto.

Solo `Create`: la richiesta è un semplice contatto, il pacchetto vero viene
creato in seguito dall'amministratore.
"""

from pydantic import BaseModel, EmailStr
from typing import Optional, Literal

TipoPacchetto = Literal["intro", "team", "tour"]


class PacchettoRichiestaCreate(BaseModel):
    nome: str
    email: EmailStr
    discord_tag: Optional[str] = None
    tipo: TipoPacchetto
    messaggio: Optional[str] = None
