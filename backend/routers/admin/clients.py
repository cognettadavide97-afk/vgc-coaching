"""Gestione clienti: elenco con statistiche, cancellazione e note tecniche."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from backend.database import get_db
from backend.models.booking import Booking
from backend.models.users import User
from backend.models.client_note import ClientNote
from backend.models.package import Package
from backend.schemas.client_note import ClientNoteCreate, ClientNoteResponse
from backend.routers.admin import get_admin
from backend.services.booking_service import libera_slot_prenotazione
from backend.services.pagination_service import pagina_e_offset, busta_paginazione
from typing import List

router = APIRouter()


# ─── LISTA CLIENTI ───────────────────────────────────────────
@router.get("/clienti")
def get_clienti(
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db),
    pagina: int = 1,
    per_pagina: int = 20
):
    """Elenca i clienti paginati, con sessioni effettuate e totale speso.

    Le statistiche sono calcolate con tre query aggregate sull'intera
    pagina, non con una query per cliente: quest'ultima soluzione
    costerebbe una query in più per ogni riga mostrata.
    """
    pagina, per_pagina, offset = pagina_e_offset(pagina, per_pagina)

    totale = db.query(User).count()

    clienti = db.query(User).order_by(User.id) \
        .offset(offset) \
        .limit(per_pagina) \
        .all()

    id_clienti_pagina = [c.id for c in clienti]

    # Il filtro sugli id della pagina evita di calcolare le statistiche
    # per l'intero archivio clienti quando ne vengono mostrati venti.
    stats_prenotazioni = dict(
        db.query(
            Booking.user_id,
            func.count(Booking.id)
        ).filter(Booking.user_id.in_(id_clienti_pagina))
        .group_by(Booking.user_id).all()
    )
    spesa_prenotazioni = dict(
        db.query(
            Booking.user_id,
            func.sum(Booking.price_cents)
        ).filter(Booking.user_id.in_(id_clienti_pagina))
        .group_by(Booking.user_id).all()
    )
    conteggio_note = dict(
        db.query(
            ClientNote.user_id,
            func.count(ClientNote.id)
        ).filter(ClientNote.user_id.in_(id_clienti_pagina))
        .group_by(ClientNote.user_id).all()
    )

    risultato = [
        {
            "id": c.id,
            "nome": c.nome,
            "email": c.email,
            "categoria": c.categoria,
            "discord": c.discord_tag,
            "telefono": c.telefono,
            # Un cliente senza prenotazioni non compare nei raggruppamenti:
            # il default copre quel caso.
            "sessioni_totali": stats_prenotazioni.get(c.id, 0),
            "totale_speso_euro": (spesa_prenotazioni.get(c.id, 0) or 0) / 100,
            "note_totali": conteggio_note.get(c.id, 0),
            "registrato_il": c.created_at.strftime("%d/%m/%Y")
        }
        for c in clienti
    ]

    return busta_paginazione(risultato, totale, pagina, per_pagina)

# ─── CANCELLAZIONE CLIENTE (diritto all'oblio, Art. 17 GDPR) ─
@router.delete("/clienti/{user_id}")
def elimina_cliente(
    user_id: int,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """Cancella definitivamente un cliente e tutti i dati collegati.

    Rimuove recensioni, prenotazioni, note e pacchetti. Le prenotazioni
    ancora confermate vengono prima liberate, così slot ed eventi sul
    calendario non restano occupati.

    Implementa il diritto alla cancellazione dichiarato nell'informativa
    privacy: è un'azione irreversibile, senza conferma lato server.
    """
    cliente = db.query(User).filter(User.id == user_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente non trovato")

    # joinedload evita una query per prenotazione nel ciclo sottostante.
    prenotazioni = db.query(Booking).options(joinedload(Booking.review)).filter(Booking.user_id == user_id).all()
    for p in prenotazioni:
        if p.status == "confirmed":
            libera_slot_prenotazione(p, db)
        # La recensione referenzia la prenotazione: va eliminata prima,
        # altrimenti il vincolo di chiave esterna blocca la cancellazione.
        if p.review:
            db.delete(p.review)
        db.delete(p)

    # I pacchetti si possono rimuovere solo ora: erano referenziati dalle
    # prenotazioni, eliminate al passo precedente.
    db.query(ClientNote).filter(ClientNote.user_id == user_id).delete()
    db.query(Package).filter(Package.user_id == user_id).delete()

    nome_cliente = cliente.nome
    db.delete(cliente)
    db.commit()
    return {"message": f"Cliente {nome_cliente} e tutti i dati collegati sono stati eliminati"}


@router.get("/clienti/{user_id}/note", response_model=List[ClientNoteResponse])
def get_note_cliente(
    user_id: int,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """Restituisce lo storico delle note di un cliente, dalla più vecchia."""
    cliente = db.query(User).filter(User.id == user_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente non trovato")

    return db.query(ClientNote).filter(
        ClientNote.user_id == user_id
    ).order_by(ClientNote.created_at.asc()).all()

@router.post("/clienti/{user_id}/note", response_model=ClientNoteResponse)
def crea_nota_cliente(
    user_id: int,
    nota: ClientNoteCreate,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """Aggiunge una nota allo storico di un cliente.

    Le note si accumulano: questa non sostituisce le precedenti.
    """
    cliente = db.query(User).filter(User.id == user_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente non trovato")

    # Una nota di soli spazi non è una nota valida.
    if not nota.nota.strip():
        raise HTTPException(status_code=400, detail="La nota non può essere vuota")

    db_nota = ClientNote(user_id=user_id, nota=nota.nota.strip())
    db.add(db_nota)
    db.commit()
    db.refresh(db_nota)
    return db_nota
