"""Endpoint pubblico delle ore prenotabili (decisione P9, pezzo 4.4).

Sostituisce, per il sito, la lettura della tabella slots: le ore si
calcolano a ogni richiesta da regole, blocchi, prenotazioni e impegni Google
(services/disponibilita_service.py). GET /slots/ resta fino al pezzo 4.6 per
le pagine vecchie ancora nella cache dei browser.
"""

from datetime import timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.services.calendar_service import CalendarioNonRaggiungibile
from backend.services.disponibilita_service import disponibilita_pubblica

router = APIRouter(prefix="/disponibilita", tags=["Disponibilità"])


@router.get("/")
def get_disponibilita(db: Session = Depends(get_db)):
    """Inizi prenotabili per durata: {"1": [...], "2": [...]}, ordinati.

    Pubblico, come GET /slots/: serve al form di prenotazione, che non
    richiede login. Gli orari portano l'offset UTC esplicito, come
    SlotResponse: senza, il JavaScript li leggerebbe nel fuso del browser.
    """
    try:
        libere = disponibilita_pubblica(db)
    except CalendarioNonRaggiungibile:
        # Nel dubbio nessun orario (decisione del pezzo 4.1): un'agenda
        # Google letta come vuota metterebbe in vendita ore occupate.
        raise HTTPException(status_code=503, detail="Availability temporarily unavailable")
    return {
        str(durata): [inizio.replace(tzinfo=timezone.utc).isoformat() for inizio in inizi]
        for durata, inizi in libere.items()
    }
