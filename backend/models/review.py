# Rappresenta il voto/commento lasciato da un cliente dopo una sessione.
# Una prenotazione può avere AL MASSIMO una recensione (booking_id è
# unique): il link inviato via email (vedi backend/scheduler.py) è
# monouso, non ha senso poter votare due volte la stessa sessione.

from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from backend.database import Base


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False, unique=True)
    voto = Column(Integer, nullable=False)  # 1-5, validato lato schema Pydantic prima di arrivare qui
    commento = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())

    # uselist=False: senza questa opzione SQLAlchemy tratterebbe
    # booking.review come una LISTA (il caso più comune per un backref è
    # "uno a molti") — qui invece booking_id è unique sopra, quindi la
    # relazione è davvero uno a uno: booking.review deve essere un singolo
    # oggetto Review o None, non una lista.
    booking = relationship("Booking", backref=backref("review", uselist=False))
