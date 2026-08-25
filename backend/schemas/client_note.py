# Vedi backend/schemas/users.py per la spiegazione generale degli schemi
# Pydantic. Questo file è il più semplice del progetto: solo due campi,
# nessuna validazione speciale.

from pydantic import BaseModel
from datetime import datetime


class ClientNoteCreate(BaseModel):
    # Un solo campo obbligatorio: il testo della nota. user_id NON è qui
    # perché non arriva dal corpo della richiesta — arriva dall'URL stesso
    # (es. POST /admin/clienti/5/note), come vedrai in backend/routers/admin/clients.py.
    nota: str


class ClientNoteResponse(BaseModel):
    id: int
    user_id: int
    nota: str
    created_at: datetime  # usato dal frontend per ordinare le note in ordine cronologico

    class Config:
        from_attributes = True
