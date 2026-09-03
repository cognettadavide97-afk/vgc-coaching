"""Assegnazione e consultazione dei pacchetti di sessioni."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.users import User
from backend.models.package import Package
from backend.schemas.package import PackageCreate, PackageResponse
from backend.routers.admin import get_admin
from backend.services.package_service import CATALOGO_PACCHETTI
from typing import List

router = APIRouter()


# Il pagamento avviene fuori dall'applicazione: il pacchetto va assegnato
# solo dopo averlo incassato. Da quel momento il cliente lo vede fra i
# propri pacchetti attivi e può spenderne le sessioni.
@router.get("/pacchetti", response_model=List[PackageResponse])
def lista_pacchetti(
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """Tutti i pacchetti assegnati, più recenti prima."""
    return db.query(Package).order_by(Package.created_at.desc()).all()

@router.post("/pacchetti", response_model=PackageResponse)
def crea_pacchetto(
    pacchetto: PackageCreate,
    admin: str = Depends(get_admin),
    db: Session = Depends(get_db)
):
    """Assegna a un cliente un pacchetto del catalogo.

    Sessioni, durata e prezzo sono letti dal catalogo in base al tipo, mai
    accettati dal client: le condizioni del pacchetto non sono alterabili
    da una richiesta.
    """
    utente = db.query(User).filter(User.id == pacchetto.user_id).first()
    if not utente:
        raise HTTPException(status_code=404, detail="Cliente non trovato")

    dati_catalogo = CATALOGO_PACCHETTI[pacchetto.tipo]

    db_pacchetto = Package(
        user_id=pacchetto.user_id,
        tipo=pacchetto.tipo,
        sessioni_totali=dati_catalogo["sessioni_totali"],
        durata_sessione_ore=dati_catalogo["durata_sessione_ore"],
        prezzo_cents=dati_catalogo["prezzo_cents"]
    )
    db.add(db_pacchetto)
    db.commit()
    db.refresh(db_pacchetto)
    return db_pacchetto
