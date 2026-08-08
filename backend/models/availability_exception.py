# Rappresenta un blocco eccezionale su un periodo di date (es. le ferie del
# coach). A differenza di AvailabilityRule (che genera slot nuovi), questo
# model serve solo a "spegnere" gli slot già esistenti che cadono nel
# periodo indicato — la logica che lo applica è in
# backend/services/availability_service.py.

from sqlalchemy import Column, Integer, Date, String, DateTime
from sqlalchemy.sql import func
from backend.database import Base


class AvailabilityException(Base):
    __tablename__ = "availability_exceptions"

    id = Column(Integer, primary_key=True, index=True)

    # Date (non DateTime!) rappresenta solo un giorno del calendario, senza
    # nessun orario — ha senso per delle ferie: "dal 10 al 20 agosto", non
    # un orario preciso di inizio/fine. "civile" nel commento originale
    # vuol dire che questa data va letta come giorno solare italiano
    # (Europe/Rome), non come data UTC.
    data_inizio = Column(Date, nullable=False)  # inclusiva: il giorno stesso conta
    data_fine = Column(Date, nullable=False)    # inclusiva: il giorno stesso conta

    motivo = Column(String(200), nullable=True)  # es. "Ferie", "Torneo X" — solo per il coach, opzionale
    created_at = Column(DateTime, default=func.now())
