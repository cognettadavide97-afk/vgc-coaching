from sqlalchemy import Column, Integer, DateTime, Boolean
from sqlalchemy.sql import func
from backend.database import Base

class Slot(Base):
    __tablename__ = "slots"

    id = Column(Integer, primary_key=True, index=True)
    start_time = Column(DateTime, nullable=False)  # data e ora inizio
    duration_hours = Column(Integer, nullable=False, default=1)  # durata in ore
    is_available = Column(Boolean, default=True)  # True = libero, False = prenotato
    created_at = Column(DateTime, default=func.now())