"""Moderazione delle recensioni lasciate dai clienti."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from backend.database import get_db
from backend.models.review import Review
from backend.models.booking import Booking
from backend.schemas.review import ReviewApprovazione
from backend.routers.admin import get_admin
from typing import Optional

router = APIRouter()


# Una recensione non è pubblica finché non viene approvata da qui: solo le
# approvate compaiono nella vetrina pubblica.
@router.get("/recensioni")
def lista_recensioni(
    approvata: Optional[bool] = None,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """Elenca le recensioni, più recenti prima, con il contesto del cliente.

    Il parametro `approvata` filtra per stato di moderazione; se omesso le
    restituisce tutte.
    """
    # joinedload evita due query aggiuntive per ogni recensione nel ciclo.
    query = db.query(Review).options(
        joinedload(Review.booking).joinedload(Booking.user)
    )
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
