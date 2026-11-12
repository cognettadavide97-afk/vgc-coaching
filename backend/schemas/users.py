"""Schemi Pydantic per gli utenti.

Gli schemi descrivono i messaggi JSON scambiati dall'API e sono distinti
dai model SQLAlchemy: quello che il client invia non coincide con quello
che il server restituisce, né con quello che è salvato nel database.
"""

from pydantic import AfterValidator, ConfigDict, BaseModel, EmailStr
from datetime import datetime
from typing import Annotated, Optional, Literal

Categoria = Literal["junior", "senior", "master"]

# Email valida (altrimenti 422) e tutta in minuscolo: è la forma con cui
# ogni email entra nel sistema, dal form, dalla prenotazione e dal login
# Discord (discord_auth.py). EmailStr da solo abbassa solo il dominio, e i
# due confronti sull'email non seguono la stessa regola: MySQL (collation
# utf8mb4_0900_ai_ci) ignora le maiuscole, Python (booking.py:125) no. Un
# cliente che scriveva "Mario@example.com" ritrovava su MySQL l'account
# "mario@example.com" e poi riceveva 403 dal confronto in Python (voce 9).
# Con un'unica forma i due giudici vedono lo stesso testo. Abbassare anche
# la parte prima della @ è un compromesso: lo standard la permetterebbe
# sensibile alle maiuscole, nessun provider in uso la tratta così.
EmailNormalizzata = Annotated[EmailStr, AfterValidator(str.lower)]


class UserCreate(BaseModel):
    """Dati accettati per creare (o ritrovare) un utente."""
    nome: str
    email: EmailNormalizzata
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

    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    """Profilo completo, restituito solo su endpoint autenticati."""
    id: int
    nome: str
    email: str
    telefono: Optional[str]
    categoria: Optional[str]
    discord_tag: Optional[str]
    created_at: datetime

    # from_attributes consente di costruire lo schema direttamente da un
    # oggetto SQLAlchemy, così un endpoint può restituire il model così
    # com'è.
    model_config = ConfigDict(from_attributes=True)
