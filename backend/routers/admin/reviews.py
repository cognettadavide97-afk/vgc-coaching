# Approvazione recensioni dal pannello admin. Vedi
# backend/routers/admin/__init__.py per la spiegazione generale del
# pacchetto.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.review import Review
from backend.schemas.review import ReviewApprovazione
from backend.routers.admin import get_admin
from typing import Optional

router = APIRouter()


# ─── RECENSIONI ──────────────────────────────────────────────
# Una recensione lasciata dal cliente (vedi POST /bookings/{id}/recensione
# in backend/routers/booking.py) non è subito pubblica: il coach la vede
# qui, e decide se approvarla prima che compaia nella vetrina pubblica
# (GET /bookings/recensioni/pubbliche, mostrata in frontend/about.html).
@router.get("/recensioni")
def lista_recensioni(
    approvata: Optional[bool] = None,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """
    Tutte le recensioni, più recenti prima — con il contesto del cliente e
    della sessione, per aiutare il coach a decidere se approvarle.
    approvata=true/false filtra solo quelle già approvate/in attesa; senza
    il parametro le mostra tutte.
    """
    query = db.query(Review)
    if approvata is not None:
        query = query.filter(Review.approvata == approvata)

    recensioni = query.order_by(Review.created_at.desc()).all()

    return [
        {
            "id": r.id,
            "voto": r.voto,
            "commento": r.commento,
            "approvata": r.approvata,
            "created_at": r.created_at.strftime("%d/%m/%Y %H:%M"),
            "cliente": {
                "nome": r.booking.user.nome,
                "email": r.booking.user.email
            },
            "servizio": r.booking.service_type
        }
        for r in recensioni
    ]


@router.patch("/recensioni/{recensione_id}")
def approva_recensione(
    recensione_id: int,
    dati: ReviewApprovazione,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """Approva (o ritira l'approvazione di) una recensione."""
    recensione = db.query(Review).filter(Review.id == recensione_id).first()
    if not recensione:
        raise HTTPException(status_code=404, detail="Recensione non trovata")

    recensione.approvata = dati.approvata
    db.commit()
    db.refresh(recensione)
    return recensione
