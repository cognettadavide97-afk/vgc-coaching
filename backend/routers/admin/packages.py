# Assegnazione pacchetti sessioni dal pannello admin. Vedi
# backend/routers/admin/__init__.py per la spiegazione generale del
# pacchetto.

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


# ─── PACCHETTI SESSIONI ────────────────────────────────────────
# Il pagamento di un pacchetto avviene fuori dall'app (come per le
# prenotazioni singole): l'admin lo assegna qui SOLO dopo aver ricevuto il
# pagamento privatamente (es. su Discord), scegliendo uno dei 3 tipi fissi
# del catalogo (backend/services/package_service.py). Da quel momento il
# cliente vede il pacchetto attivo sul form pubblico (GET /pacchetti/attivi
# in backend/routers/users.py) e può spenderne le sessioni prenotando slot.
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
    """
    Assegna a un cliente esistente un pacchetto del catalogo fisso.
    Sessioni totali, durata e prezzo NON arrivano dal client: vengono presi
    dal catalogo in base a "tipo", esattamente come TABELLA_PREZZI in
    backend/routers/booking.py per le prenotazioni singole.
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
