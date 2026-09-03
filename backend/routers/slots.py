"""Endpoint sugli slot di disponibilità.

La lettura è pubblica (serve al form di prenotazione, che non richiede
login), la scrittura è riservata all'amministratore.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.slots import Slot
from backend.schemas.slots import SlotCreate, SlotResponse
from backend.routers.admin import get_admin
from backend.services.availability_service import slot_si_sovrappone
from backend.services.timezone_service import ora_utc_naive
from typing import List

router = APIRouter(prefix="/slots", tags=["Slots"])


@router.get("/", response_model=List[SlotResponse])
def get_slots(db: Session = Depends(get_db)):
    """Elenca gli slot prenotabili: liberi e non ancora iniziati.

    Endpoint pubblico, senza autenticazione.
    """
    # Il filtro sull'orario è necessario oltre a quello su is_available:
    # nessun processo marca gli slot come scaduti, quindi uno slot passato e
    # mai prenotato resta is_available=True a tempo indefinito.
    ora_utc = ora_utc_naive()
    slots = db.query(Slot).filter(
        Slot.is_available == True,
        Slot.start_time >= ora_utc
    ).all()
    return slots


@router.post("/", response_model=SlotResponse)
def create_slot(slot: SlotCreate, admin: str = Depends(get_admin), db: Session = Depends(get_db)):
    """Crea un singolo slot di disponibilità.

    Riservato all'amministratore. Restituisce 400 se il nuovo slot si
    sovrappone a uno esistente.
    """
    if slot_si_sovrappone(db, slot.start_time, slot.duration_hours):
        raise HTTPException(
            status_code=400,
            detail="Questo slot si sovrappone a uno slot già esistente"
        )

    # start_time arriva già convertito in UTC dal validator di SlotCreate.
    db_slot = Slot(
        start_time=slot.start_time,
        duration_hours=slot.duration_hours
    )
    db.add(db_slot)
    db.commit()
    db.refresh(db_slot)
    return db_slot
