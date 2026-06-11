from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False)
    stripe_session_id = Column(String(200), nullable=True)  # ID della sessione Stripe
    amount_cents = Column(Integer, nullable=False)
    status = Column(String(20), default="pending")  # pending, completed, failed
    created_at = Column(DateTime, default=func.now())

    booking = relationship("Booking", backref="payment")