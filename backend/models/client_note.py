"""Model della tabella `client_notes`: le note tecniche del coach sui clienti.

Tabella separata e non campo su `User` perché le note si accumulano nel
tempo e vanno conservate tutte come storico.
"""

from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base
from backend.services.timezone_service import ora_utc_naive


class ClientNote(Base):
    __tablename__ = "client_notes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    nota = Column(Text, nullable=False)
    created_at = Column(DateTime, default=ora_utc_naive)  # usato anche per l'ordinamento cronologico

    user = relationship("User", backref="note_tecniche")
