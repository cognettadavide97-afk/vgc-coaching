# Gestione clienti dal pannello admin: lista con statistiche, cancellazione
# (diritto all'oblio GDPR), e note tecniche (mini-CRM). Vedi
# backend/routers/admin/__init__.py per la spiegazione generale del
# pacchetto.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
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
    """
    Restituisce i clienti, paginati, con il numero di sessioni
    effettuate e il totale speso. Le statistiche per cliente sono
    calcolate con query aggregate (GROUP BY), non con un ciclo
    Python che interroga il DB una volta per cliente (N+1).
    """
    # Il problema "N+1" che il commento sopra nomina è un classico errore
    # di prestazioni: se per ogni cliente (N clienti) facessimo una query
    # separata per contare le sue prenotazioni, otterremmo 1 query per la
    # lista clienti PIÙ N query aggiuntive (una per cliente) — con 100
    # clienti, 101 query invece di poche. La soluzione sotto fa UNA query
    # che raggruppa e conta tutto insieme, per tutti i clienti della pagina
    # contemporaneamente.
    pagina, per_pagina, offset = pagina_e_offset(pagina, per_pagina)

    totale = db.query(User).count()

    clienti = db.query(User).order_by(User.id) \
        .offset(offset) \
        .limit(per_pagina) \
        .all()

    id_clienti_pagina = [c.id for c in clienti]

    # .group_by(Booking.user_id) raggruppa tutte le prenotazioni per
    # cliente, e func.count(Booking.id) conta quante righe ci sono in ogni
    # gruppo — è l'equivalente SQL di "per ogni cliente, quante
    # prenotazioni ha". Il risultato è una lista di coppie (user_id,
    # conteggio); dict(...) la trasforma in un dizionario {user_id:
    # conteggio}, comodo da consultare subito dopo con .get(cliente.id).
    #
    # .filter(Booking.user_id.in_(id_clienti_pagina)) limita il calcolo
    # solo ai clienti della pagina corrente — non ha senso calcolare le
    # statistiche di TUTTI i clienti se ne stiamo mostrando solo 20.
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
            # .get(c.id, 0): se questo cliente non compare nel dizionario
            # (perché non ha nessuna prenotazione, quindi group_by non
            # produce nessuna riga per lui), il default 0 evita un errore.
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
    """
    Cancella definitivamente un cliente e tutti i dati collegati:
    recensioni, prenotazioni, note tecniche e pacchetti. Prima di
    cancellare, libera lo slot (ed elimina l'evento Google Calendar) di
    ogni prenotazione ancora "confirmed" — stessa funzione già usata da
    PATCH /admin/prenotazioni/{id}/stato quando una prenotazione viene
    cancellata singolarmente.

    Da usare quando un cliente esercita il diritto alla cancellazione dei
    propri dati (vedi frontend/privacy.html, sezione "I tuoi diritti") —
    finora l'unico modo per farlo era intervenire a mano sul database.
    """
    cliente = db.query(User).filter(User.id == user_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente non trovato")

    prenotazioni = db.query(Booking).filter(Booking.user_id == user_id).all()
    for p in prenotazioni:
        if p.status == "confirmed":
            libera_slot_prenotazione(p, db)
        # Una recensione ha una ForeignKey verso la sua prenotazione (vedi
        # backend/models/review.py): va cancellata PRIMA della prenotazione
        # a cui appartiene, altrimenti il database rifiuterebbe di
        # eliminare una riga ancora referenziata da un'altra.
        if p.review:
            db.delete(p.review)
        db.delete(p)

    # Stesso motivo per cui le prenotazioni vanno cancellate prima dei
    # pacchetti: Booking.package_id referenzia packages.id (vedi
    # backend/models/booking.py) — a questo punto le prenotazioni sono già
    # state eliminate sopra, quindi i pacchetti si possono rimuovere senza
    # violare nessun vincolo.
    db.query(ClientNote).filter(ClientNote.user_id == user_id).delete()
    db.query(Package).filter(Package.user_id == user_id).delete()

    nome_cliente = cliente.nome
    db.delete(cliente)
    db.commit()
    return {"message": f"Cliente {nome_cliente} e tutti i dati collegati sono stati eliminati"}


# ─── NOTE TECNICHE CLIENTE (MINI-CRM) ────────────────────────
@router.get("/clienti/{user_id}/note", response_model=List[ClientNoteResponse])
def get_note_cliente(
    user_id: int,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Restituisce lo storico delle note tecniche di un cliente,
    in ordine cronologico (dalla più vecchia alla più recente).
    """
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
    """
    Aggiunge una nuova nota tecnica allo storico di un cliente
    (es. "Fatica a gestire i team Trick Room") — non sostituisce
    le note precedenti, si accumulano nel tempo.
    """
    cliente = db.query(User).filter(User.id == user_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente non trovato")

    # .strip() rimuove spazi bianchi/a-capo all'inizio e alla fine di una
    # stringa — una nota fatta solo di spazi non deve contare come "non
    # vuota".
    if not nota.nota.strip():
        raise HTTPException(status_code=400, detail="La nota non può essere vuota")

    db_nota = ClientNote(user_id=user_id, nota=nota.nota.strip())
    db.add(db_nota)
    db.commit()
    db.refresh(db_nota)
    return db_nota
