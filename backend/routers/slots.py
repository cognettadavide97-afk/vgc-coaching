"""Endpoint pubblico sugli slot, solo per le pagine vecchie.

Le pagine del sito precedenti al pezzo 4.4, ancora nella cache dei
browser, leggono qui la lista degli slot. Il sito di oggi legge
GET /disponibilita/. Questo endpoint sparisce nel 4.6b; la creazione a mano
degli slot (POST /slots/), che dal 4.4 creava ore impossibili da vendere, è
sparita nel 4.6a.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.slots import Slot
from backend.schemas.slots import SlotResponse
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
    #
    # L'ordinamento è esplicito e non lasciato al database. Senza, MySQL in
    # produzione restituiva gli slot raggruppati per regola di
    # disponibilità invece che per data: la generazione notturna scorre una
    # regola alla volta, quindi tutti i lunedì vengono inseriti prima di
    # tutti i mercoledì. Il form pubblico li mostra nell'ordine in cui
    # arrivano, e il cliente vedeva le date saltare avanti e indietro --
    # dal 30 settembre all'8, e così via.
    #
    # Osservato in produzione il 2026-09-07: 8 salti all'indietro su 83
    # slot. Non era emerso dai test perché SQLite, con lo stesso indice,
    # sceglie un piano che restituisce le righe già ordinate: è la
    # differenza fra i due database, non la query, a nascondere il difetto.
    ora_utc = ora_utc_naive()
    slots = db.query(Slot).filter(
        Slot.is_available == True,
        Slot.start_time >= ora_utc
    ).order_by(Slot.start_time).all()
    return slots
