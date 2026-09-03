"""Schema Pydantic per la richiesta di consulenza gratuita.

Solo `Create`: l'endpoint risponde con un messaggio fisso e non restituisce
una risorsa, quindi non serve uno schema di risposta.
"""

from pydantic import BaseModel, EmailStr
from typing import Optional


class ConsulenzaCreate(BaseModel):
    nome: str
    email: EmailStr
    discord_tag: Optional[str] = None
    messaggio: Optional[str] = None
