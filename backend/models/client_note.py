# Rappresenta UNA nota tecnica che il coach scrive su un cliente (es.
# "Fatica a gestire i team Trick Room"). Nota che questa è una tabella
# separata da User, non un campo dentro User — perché un cliente può avere
# MOLTE note nel tempo, e vogliamo tenerle tutte (uno storico), non solo
# l'ultima. Questo è un pattern comune: quando un dato può ripetersi un
# numero qualsiasi di volte per la stessa "cosa", diventa una tabella a
# parte collegata con una ForeignKey, invece di un singolo campo.

from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base


class ClientNote(Base):
    __tablename__ = "client_notes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # a quale cliente appartiene
    nota = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())  # usato anche per ordinare le note in ordine cronologico

    user = relationship("User", backref="note_tecniche")
