# Vedi backend/routers/users.py per la spiegazione generale di un router
# FastAPI. Questo file gestisce gli slot: vederli (per il form pubblico) e
# crearli (solo il coach può farlo).

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


# Nota che questo endpoint NON ha nessun Depends(get_admin): è
# volutamente pubblico, perché deve poterlo chiamare chiunque visiti il
# form di prenotazione, anche senza aver fatto login.
@router.get("/", response_model=List[SlotResponse])
def get_slots(db: Session = Depends(get_db)):
    # .filter(Slot.is_available == True) mostra SOLO gli slot ancora
    # liberi — chi prenota non deve vedere (né poter scegliere) uno slot
    # già occupato o bloccato. Il secondo filtro esclude anche gli slot
    # liberi ma il cui orario è già passato (mai prenotati, quindi ancora
    # "disponibili" per il database, ma non ha senso proporli): stesso
    # confronto naive-UTC usato in booking.py e nel package admin/.
    ora_utc = ora_utc_naive()
    slots = db.query(Slot).filter(
        Slot.is_available == True,
        Slot.start_time >= ora_utc
    ).all()
    return slots


@router.get("/{slot_id}", response_model=SlotResponse)
def get_slot(slot_id: int, db: Session = Depends(get_db)):
    # "{slot_id}" nel percorso dell'endpoint è un "path parameter": la
    # parte variabile dell'URL (es. /slots/42) diventa automaticamente il
    # parametro slot_id della funzione, già convertito al tipo giusto (int)
    # — se qualcuno chiamasse /slots/abc, FastAPI rifiuterebbe la richiesta
    # da solo, prima ancora di eseguire questa funzione.
    slot = db.query(Slot).filter(Slot.id == slot_id).first()
    if not slot:
        # HTTPException è come si comunica un errore HTTP da un endpoint
        # FastAPI: status_code è il codice standard (404 = "non trovato"),
        # detail è il messaggio che il client riceverà nel corpo della
        # risposta. Sollevarla (raise) interrompe subito l'esecuzione della
        # funzione, la riga "return slot" più sotto non verrebbe mai raggiunta.
        raise HTTPException(status_code=404, detail="Slot not found")
    return slot


# Qui invece admin: str = Depends(get_admin) protegge l'endpoint: solo il
# coach (con un token JWT admin valido) può creare nuovi slot.
@router.post("/", response_model=SlotResponse)
def create_slot(slot: SlotCreate, admin: str = Depends(get_admin), db: Session = Depends(get_db)):
    # Prima di salvare, controlliamo che questo nuovo slot non si sovrapponga
    # a uno slot già esistente (vedi la spiegazione dettagliata di questa
    # funzione in backend/services/availability_service.py) — impedisce al
    # coach di creare per sbaglio due slot che si accavallano nel tempo.
    if slot_si_sovrappone(db, slot.start_time, slot.duration_hours):
        raise HTTPException(
            status_code=400,
            detail="Questo slot si sovrappone a uno slot già esistente"
        )

    # slot.start_time qui è già stato convertito in UTC dal validator dentro
    # SlotCreate (vedi backend/schemas/slots.py) — quando questo codice gira,
    # la conversione è già avvenuta automaticamente, prima ancora che questa
    # funzione venga chiamata.
    db_slot = Slot(
        start_time=slot.start_time,
        duration_hours=slot.duration_hours
    )
    db.add(db_slot)
    db.commit()
    db.refresh(db_slot)
    return db_slot
