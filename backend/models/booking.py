from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    slot_id = Column(Integer, ForeignKey("slots.id"), nullable=False)
    duration_hours = Column(Integer, nullable=False, default=1)
    price_cents = Column(Integer, nullable=False)  # prezzo in centesimi (es. 3500 = €35)
    status = Column(String(20), default="pending")  # pending, confirmed, cancelled
    note_cliente = Column(Text, nullable=True)
    note_admin = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())

    # relazioni — permettono di accedere ai dati collegati
    user = relationship("User", backref="bookings")
    slot = relationship("Slot", backref="booking")