"""Schemi Pydantic per le note tecniche sui clienti."""

from pydantic import BaseModel
from datetime import datetime


class ClientNoteCreate(BaseModel):
    # `user_id` non compare: arriva dal path dell'endpoint
    # (POST /admin/clienti/{user_id}/note), non dal corpo della richiesta.
    nota: str


class ClientNoteResponse(BaseModel):
    id: int
    user_id: int
    nota: str
    created_at: datetime

    class Config:
        from_attributes = True
