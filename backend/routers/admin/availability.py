# Gestione della disponibilità dal pannello admin: slot singoli (vederli,
# sincronizzarli col calendario Google, eliminarli), regole ricorrenti
# ("ogni martedì 18-22") e blocchi eccezionali (ferie). Vedi
# backend/routers/admin/__init__.py per la spiegazione generale del
# pacchetto.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.booking import Booking
from backend.models.slots import Slot
from backend.models.availability_rule import AvailabilityRule
from backend.models.availability_exception import AvailabilityException
from backend.schemas.availability import (
    AvailabilityRuleCreate, AvailabilityRuleResponse,
    AvailabilityExceptionCreate, AvailabilityExceptionResponse
)
from backend.routers.admin import get_admin
from backend.services.calendar_service import sincronizza_slot_con_calendario
from backend.services.timezone_service import formatta_data_ora_rome
from backend.services.availability_service import genera_slot_da_regola, applica_blocco_eccezionale
from backend.services.pagination_service import pagina_e_offset, busta_paginazione
from typing import List

router = APIRouter()


# ─── GESTIONE SLOT ───────────────────────────────────────────
@router.get("/slots")
def get_slots_admin(
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db),
    pagina: int = 1,
    per_pagina: int = 20
):
    """Restituisce gli slot, liberi e occupati, paginati (più vicini nel tempo prima)."""
    pagina, per_pagina, offset = pagina_e_offset(pagina, per_pagina)

    totale = db.query(Slot).count()

    slots = db.query(Slot).order_by(Slot.start_time) \
        .offset(offset) \
        .limit(per_pagina) \
        .all()

    items = []
    for s in slots:
        data, ora = formatta_data_ora_rome(s.start_time)
        items.append({
            "id": s.id,
            "data": data,
            "ora": ora,
            "durata_ore": s.duration_hours,
            "disponibile": s.is_available,
            "bloccato_da_calendario": s.blocked_external,
            "bloccato_da_admin": s.blocked_admin
        })

    return busta_paginazione(items, totale, pagina, per_pagina)

@router.post("/slots/sync-calendario")
def sincronizza_calendario(
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Legge il calendario Google del coach e blocca automaticamente
    (is_available=False, blocked_external=True) gli slot liberi che si
    sovrappongono a un evento esterno (torneo, stream, altro impegno).
    La logica vera vive in sincronizza_slot_con_calendario
    (backend/services/calendar_service.py), riusata anche dal job
    automatico periodico in backend/scheduler.py — questo endpoint resta
    per il bottone manuale nel pannello admin, comportamento identico a
    prima.
    """
    bloccati = sincronizza_slot_con_calendario(db)
    return {"slot_bloccati": bloccati}

@router.delete("/slots/{slot_id}")
def elimina_slot(
    slot_id: int,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Elimina uno slot. Se ha prenotazioni collegate (anche cancellate, anche
    come slot secondario di una sessione da 2h) la richiesta viene RIFIUTATA
    con un 400 e lo slot resta esattamente com'è: si preserva lo storico non
    toccandolo. Nessuna "disattivazione" automatica — per rendere uno slot
    non prenotabile senza cancellarlo esiste il blocco eccezionale
    (POST /admin/disponibilita/blocchi).
    """
    slot = db.query(Slot).filter(Slot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot non trovato")

    # controlla se esistono prenotazioni collegate a questo slot — anche
    # come slot_id_secondario, cioè la "seconda ora" di una sessione da 2h
    # (vedi backend/models/booking.py): entrambe le colonne sono una
    # ForeignKey verso slots.id, quindi il database rifiuterebbe comunque
    # la cancellazione con un errore tecnico se controllassimo solo
    # slot_id — questo controllo dà invece il messaggio chiaro sotto.
    prenotazioni_collegate = db.query(Booking).filter(
        or_(Booking.slot_id == slot_id, Booking.slot_id_secondario == slot_id)
    ).count()

    if prenotazioni_collegate > 0:
        # Perché non permettere comunque l'eliminazione? Perché slot_id in
        # Booking è una ForeignKey (vedi backend/models/booking.py): il
        # database stesso impedirebbe di eliminare uno slot ancora
        # referenziato da qualche prenotazione (per non lasciare
        # prenotazioni "orfane", che puntano a uno slot inesistente).
        # Controllarlo qui PRIMA di provare a cancellare permette di dare
        # un messaggio d'errore chiaro, invece di un errore tecnico del
        # database poco comprensibile.
        raise HTTPException(
            status_code=400,
            detail=f"Impossibile eliminare: questo slot ha {prenotazioni_collegate} prenotazione/i collegate nello storico. Non può essere rimosso per preservare i dati."
        )

    db.delete(slot)
    db.commit()
    return {"message": "Slot eliminato"}

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

@router.post("/disponibilita/regole")
def crea_regola_disponibilita(
    regola: AvailabilityRuleCreate,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Crea una regola di disponibilità ricorrente (es. "ogni martedì 18-22,
    slot da 1h") e genera subito gli slot corrispondenti fino alla fine
    del mese corrente, saltando quelli già esistenti allo stesso orario.
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

    # Dopo aver salvato LA REGOLA, chiamiamo la funzione di
    # availability_service.py che genera DAVVERO gli slot concreti a
    # partire da essa — vedi i commenti dettagliati in quel file per capire
    # come funziona il calcolo.
    slot_creati = genera_slot_da_regola(db_regola, db)

    return {
        # AvailabilityRuleResponse.model_validate(db_regola) trasforma
        # manualmente l'oggetto SQLAlchemy in uno schema Pydantic — di
        # solito questo lo fa FastAPI da solo tramite response_model, ma
        # qui la risposta è un dizionario con DUE cose diverse dentro
        # (la regola e il conteggio degli slot creati), quindi va costruito
        # a mano invece di lasciare che FastAPI usi un response_model
        # singolo.
        "regola": AvailabilityRuleResponse.model_validate(db_regola),
        "slot_creati": slot_creati
    }

@router.delete("/disponibilita/regole/{regola_id}")
def elimina_regola_disponibilita(
    regola_id: int,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Elimina una regola di disponibilità ricorrente. Non tocca gli slot
    già generati in passato — restano come slot normali indipendenti.
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

@router.post("/disponibilita/blocchi")
def crea_blocco_eccezionale(
    blocco: AvailabilityExceptionCreate,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Crea un blocco eccezionale (es. ferie) su un periodo di date e marca
    subito come non disponibili gli slot liberi che ci cadono dentro.
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

    slot_bloccati = applica_blocco_eccezionale(db_blocco, db)

    return {
        "blocco": AvailabilityExceptionResponse.model_validate(db_blocco),
        "slot_bloccati": slot_bloccati
    }

@router.delete("/disponibilita/blocchi/{blocco_id}")
def elimina_blocco_eccezionale(
    blocco_id: int,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Elimina un blocco eccezionale. Non riapre automaticamente gli slot
    che aveva bloccato — va fatto manualmente se necessario.
    """
    blocco = db.query(AvailabilityException).filter(AvailabilityException.id == blocco_id).first()
    if not blocco:
        raise HTTPException(status_code=404, detail="Blocco non trovato")

    db.delete(blocco)
    db.commit()
    return {"message": "Blocco eliminato"}
