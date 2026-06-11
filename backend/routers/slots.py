from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.slots import Slot
from backend.schemas.slots import SlotCreate, SlotResponse
from typing import List

router = APIRouter(prefix="/slots", tags=["Slots"])

@router.get("/", response_model=List[SlotResponse])
def get_slots(db: Session = Depends(get_db)):
    slots = db.query(Slot).filter(Slot.is_available == True).all()
    return slots

@router.get("/{slot_id}", response_model=SlotResponse)
def get_slot(slot_id: int, db: Session = Depends(get_db)):
    slot = db.query(Slot).filter(Slot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot non trovato")
    return slot

@router.post("/", response_model=SlotResponse)
def create_slot(slot: SlotCreate, db: Session = Depends(get_db)):
    db_slot = Slot(
        start_time=slot.start_time,
        duration_hours=slot.duration_hours
    )
    db.add(db_slot)
    db.commit()
    db.refresh(db_slot)
    return db_slot