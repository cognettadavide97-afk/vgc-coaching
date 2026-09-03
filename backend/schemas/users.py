"""Schemi Pydantic per gli utenti.

Gli schemi descrivono i messaggi JSON scambiati dall'API e sono distinti
dai model SQLAlchemy: quello che il client invia non coincide con quello
che il server restituisce, né con quello che è salvato nel database.
"""

from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, Literal

Categoria = Literal["junior", "senior", "master"]


class UserCreate(BaseModel):
    """Dati accettati per creare (o ritrovare) un utente."""
    nome: str
    email: EmailStr  # EmailStr valida il formato e respinge con 422
    telefono: Optional[str] = None
    categoria: Optional[Categoria] = None
    discord_tag: Optional[str] = None


class UserIdResponse(BaseModel):
    """Risposta di `POST /users/`: solo l'identificativo.

    L'endpoint è pubblico e si comporta da "get or create": restituire il
    profilo completo esporrebbe i dati di un cliente esistente a chiunque
    ne indovini l'email. Al client serve solo l'id per proseguire con la
    prenotazione.
    """
    id: int

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    """Profilo completo, restituito solo su endpoint autenticati."""
    id: int
    nome: str
    email: str
    telefono: Optional[str]
    categoria: Optional[str]
    discord_tag: Optional[str]
    created_at: datetime

    class Config:
        # Consente di costruire lo schema direttamente da un oggetto
        # SQLAlchemy, così un endpoint può restituire il model così com'è.
        from_attributes = True
