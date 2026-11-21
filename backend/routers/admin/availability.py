"""Gestione della disponibilità: regole ricorrenti, blocchi e anteprima.

Le regole dicono quando il coach lavora ("ogni martedì 18-22"), i blocchi
quando no (ferie). Si salvano e basta: le ore in vendita le calcola
services/disponibilita_service.py a ogni richiesta, quindi una regola o un
blocco creati o eliminati valgono subito, per il sito e per l'anteprima.

Fino al pezzo 4.6a regole e blocchi generavano e chiudevano gli slot, una
copia della disponibilità salvata in anticipo, e il pannello aveva gli
endpoint per sincronizzarli con Google, sbloccarli ed eliminarli a mano.
Dal 4.4 il sito non vendeva più gli slot; nel 4.6a sono spariti anche
questi endpoint.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.availability_rule import AvailabilityRule
from backend.models.availability_exception import AvailabilityException
from backend.schemas.availability import (
    AvailabilityRuleCreate, AvailabilityRuleResponse,
    AvailabilityExceptionCreate, AvailabilityExceptionResponse
)
from backend.routers.admin import get_admin
from backend.services.calendar_service import CalendarioNonRaggiungibile
from backend.services.timezone_service import ora_utc_naive, utc_to_rome
from backend.services.disponibilita_service import anteprima_settimana
from typing import List
from datetime import timedelta

router = APIRouter()

# Fin dove l'anteprima guarda avanti. Serve solo a rifiutare numeri assurdi:
# tre mesi sono già ben oltre l'orizzonte di vendita (GIORNI_PRENOTABILI in
# services/disponibilita_service.py).
SETTIMANE_ANTEPRIMA = 12


# ─── ANTEPRIMA SETTIMANALE ────────────────────────────────────
@router.get("/disponibilita/anteprima")
def anteprima_disponibilita(
    settimana: int = Query(0, ge=0, le=SETTIMANE_ANTEPRIMA),
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """Le ore di una settimana con il loro stato, in sola lettura (pezzo 4.5).

    `settimana` conta da questa: 0 è la settimana in corso, 1 la prossima.
    Il lunedì è quello del giorno italiano: la domenica alle 23:30 UTC, a
    Roma, è già lunedì. "In vendita" lo decide lo stesso calcolo del sito
    (anteprima_settimana in services/disponibilita_service.py).

    Google irraggiungibile è un 503, come per il sito: un'anteprima senza
    i suoi impegni mostrerebbe in vendita ore che il sito non offre.
    """
    oggi = utc_to_rome(ora_utc_naive()).date()
    lunedi = oggi - timedelta(days=oggi.weekday()) + timedelta(weeks=settimana)
    try:
        giorni = anteprima_settimana(db, lunedi)
    except CalendarioNonRaggiungibile:
        raise HTTPException(status_code=503, detail="Google Calendar non raggiungibile")
    return {"settimana": settimana, "giorni": giorni}

# ─── DISPONIBILITÀ RICORRENTE ─────────────────────────────────
@router.get("/disponibilita/regole", response_model=List[AvailabilityRuleResponse])
def lista_regole_disponibilita(
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """Restituisce tutte le regole di disponibilità ricorrente."""
    return db.query(AvailabilityRule).order_by(
        AvailabilityRule.giorno_settimana, AvailabilityRule.ora_inizio
    ).all()

@router.post("/disponibilita/regole", response_model=AvailabilityRuleResponse)
def crea_regola_disponibilita(
    regola: AvailabilityRuleCreate,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Crea una regola di disponibilità ricorrente (es. "ogni martedì 18-22")
    e la restituisce. Le sue ore libere sono in vendita da subito, fino
    all'orizzonte (GIORNI_PRENOTABILI): nessuno slot da generare.
    """
    if regola.ora_fine <= regola.ora_inizio:
        raise HTTPException(status_code=400, detail="L'ora di fine deve essere successiva all'ora di inizio")

    db_regola = AvailabilityRule(
        giorno_settimana=regola.giorno_settimana,
        ora_inizio=regola.ora_inizio,
        ora_fine=regola.ora_fine,
        durata_slot_ore=regola.durata_slot_ore
    )
    db.add(db_regola)
    db.commit()
    db.refresh(db_regola)
    return db_regola

@router.delete("/disponibilita/regole/{regola_id}")
def elimina_regola_disponibilita(
    regola_id: int,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Elimina una regola di disponibilità ricorrente. Le sue ore escono
    subito dalla vendita, perché il sito le calcola dalle regole; le
    prenotazioni già fatte restano.
    """
    regola = db.query(AvailabilityRule).filter(AvailabilityRule.id == regola_id).first()
    if not regola:
        raise HTTPException(status_code=404, detail="Regola non trovata")

    db.delete(regola)
    db.commit()
    return {"message": "Regola eliminata"}

# ─── BLOCCHI ECCEZIONALI (FERIE, ECC.) ────────────────────────
@router.get("/disponibilita/blocchi", response_model=List[AvailabilityExceptionResponse])
def lista_blocchi_eccezionali(
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """Restituisce tutti i blocchi eccezionali (ferie, indisponibilità), più recenti prima."""
    return db.query(AvailabilityException).order_by(
        AvailabilityException.data_inizio.desc()
    ).all()

@router.post("/disponibilita/blocchi", response_model=AvailabilityExceptionResponse)
def crea_blocco_eccezionale(
    blocco: AvailabilityExceptionCreate,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Crea un blocco eccezionale (es. ferie) su un periodo di giorni italiani,
    estremi inclusi, e lo restituisce. Quei giorni escono subito dalla
    vendita; le prenotazioni già fatte restano (l'anteprima le mostra).
    """
    if blocco.data_fine < blocco.data_inizio:
        raise HTTPException(status_code=400, detail="La data di fine deve essere successiva o uguale alla data di inizio")

    db_blocco = AvailabilityException(
        data_inizio=blocco.data_inizio,
        data_fine=blocco.data_fine,
        motivo=blocco.motivo
    )
    db.add(db_blocco)
    db.commit()
    db.refresh(db_blocco)
    return db_blocco

@router.delete("/disponibilita/blocchi/{blocco_id}")
def elimina_blocco_eccezionale(
    blocco_id: int,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """Elimina un blocco eccezionale.

    Quei giorni tornano subito in vendita, se una regola li prevede e sono
    liberi: il calcolo legge i blocchi a ogni richiesta, e un secondo blocco
    sovrapposto resta in vigore perché il calcolo lo legge per conto suo.
    Con gli slot, fino al 4.6a, non era così: il blocco non registrava
    quali slot avesse chiuso, e riaprirli era una decisione a mano, slot per
    slot (decisione P1, superata da P9).
    """
    blocco = db.query(AvailabilityException).filter(AvailabilityException.id == blocco_id).first()
    if not blocco:
        raise HTTPException(status_code=404, detail="Blocco non trovato")

    db.delete(blocco)
    db.commit()
    return {"message": "Blocco eliminato"}
