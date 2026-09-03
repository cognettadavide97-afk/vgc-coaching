"""Model della tabella `reviews`: le recensioni post-sessione."""

from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from backend.database import Base


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)

    # `unique` impone una sola recensione per prenotazione.
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False, unique=True)

    voto = Column(Integer, nullable=False)  # 1-5, validato dallo schema Pydantic
    commento = Column(Text, nullable=True)

    # Moderazione: una recensione resta privata finché il coach non la
    # approva. Solo le approvate compaiono nella vetrina pubblica.
    approvata = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=func.now())

    # uselist=False perché `booking_id` è unique: la relazione inversa è
    # uno-a-uno, quindi `booking.review` è un oggetto o None, non una lista.
    booking = relationship("Booking", backref=backref("review", uselist=False))
