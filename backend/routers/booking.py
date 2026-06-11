from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.booking import Booking
from backend.models.slots import Slot
from backend.models.users import User
from backend.schemas.booking import BookingCreate, BookingResponse
from backend.services.email_service import invia_conferma_cliente, invia_notifica_admin
from typing import List

router = APIRouter(prefix="/bookings", tags=["Bookings"])

PRICE_TABLE = {1: 3500, 2: 6000, 3: 8000}

@router.get("/", response_model=List[BookingResponse])
def get_bookings(db: Session = Depends(get_db)):
    return db.query(Booking).all()

@router.post("/", response_model=BookingResponse)
def create_booking(booking: BookingCreate, db: Session = Depends(get_db)):

    slot = db.query(Slot).filter(Slot.id == booking.slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot non trovato")
    if not slot.is_available:
        raise HTTPException(status_code=400, detail="Slot non disponibile")

    user = db.query(User).filter(User.id == booking.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    price = PRICE_TABLE.get(booking.duration_hours, 3500)

    db_booking = Booking(
        user_id=booking.user_id,
        slot_id=booking.slot_id,
        duration_hours=booking.duration_hours,
        price_cents=price,
        note_cliente=booking.note_cliente,
        status="pending"
    )
    db.add(db_booking)
    slot.is_available = False
    db.commit()
    db.refresh(db_booking)

    data_slot = slot.start_time.strftime("%d/%m/%Y")
    ora_slot = slot.start_time.strftime("%H:%M")

    invia_conferma_cliente(
        email_cliente=user.email,
        nome_cliente=user.nome,
        data_slot=data_slot,
        ora_slot=ora_slot,
        durata=booking.duration_hours,
        prezzo=price
    )

    invia_notifica_admin(
        nome_cliente=user.nome,
        email_cliente=user.email,
        data_slot=data_slot,
        ora_slot=ora_slot,
        durata=booking.duration_hours,
        note_cliente=booking.note_cliente
    )

    return db_booking