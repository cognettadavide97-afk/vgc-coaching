"""Endpoint sugli utenti e identità dello studente.

Espone la creazione pubblica dell'utente e, per chi è autenticato via
Discord, il proprio profilo, storico e pacchetti attivi.

Qui vivono anche le dependency `get_studente_opzionale` e `get_studente`,
usate dagli altri router per riconoscere lo studente dal cookie di
sessione.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, contains_eager
from datetime import timezone
from backend.database import get_db
from backend.models.users import User
from backend.models.booking import Booking
from backend.models.slots import Slot
from backend.models.package import Package
from backend.schemas.users import UserCreate, UserResponse, UserIdResponse
from backend.routers.admin import get_admin
from backend.services.auth_service import verifica_token_studente
from backend.services.timezone_service import formatta_data_ora_rome
from backend.services.package_service import CATALOGO_PACCHETTI
from backend.rate_limit import limiter
from typing import List, Optional

router = APIRouter(prefix="/users", tags=["Users"])

# Cookie httpOnly impostato dal server al login: non è leggibile da
# JavaScript, quindi non è esfiltrabile da uno script iniettato nella
# pagina. Il browser lo allega da solo alle richieste verso questa origine.
STUDENT_TOKEN_COOKIE = "student_token"


def get_studente_opzionale(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Restituisce lo studente autenticato dal cookie, o None.

    Da usare negli endpoint in cui il login è facoltativo.
    """
    token = request.cookies.get(STUDENT_TOKEN_COOKIE)
    if not token:
        return None
    payload = verifica_token_studente(token)
    if not payload:
        return None
    return db.query(User).filter(User.id == payload["user_id"]).first()


def get_studente(studente: Optional[User] = Depends(get_studente_opzionale)) -> User:
    """Come `get_studente_opzionale`, ma risponde 401 se manca il login."""
    if not studente:
        raise HTTPException(status_code=401, detail="Login required")
    return studente


@router.get("/", response_model=List[UserResponse])
def get_users(admin: str = Depends(get_admin), db: Session = Depends(get_db)):
    return db.query(User).all()


@router.get("/me", response_model=UserResponse)
def get_utente_corrente(studente: User = Depends(get_studente)):
    """Profilo dello studente autenticato, usato per precompilare il form."""
    return studente


@router.get("/me/prenotazioni")
def get_prenotazioni_studente(
    studente: User = Depends(get_studente),
    db: Session = Depends(get_db)
):
    """Storico delle prenotazioni dello studente, dalla più recente."""
    # Il join serve a ordinare per un campo di slots; contains_eager evita
    # che il ciclo rilegga lo slot riga per riga. La relationship va
    # indicata esplicitamente perché due colonne puntano a slots.
    prenotazioni = db.query(Booking).join(Booking.slot).options(
        contains_eager(Booking.slot)
    ).filter(
        Booking.user_id == studente.id
    ).order_by(Slot.start_time.desc()).all()

    # Risposta costruita a mano invece che con un response_model: espone
    # solo i campi utili al frontend, già formattati.
    risultato = []
    for p in prenotazioni:
        data, ora = formatta_data_ora_rome(p.slot.start_time)
        risultato.append({
            "id": p.id,
            "servizio": p.service_type,
            "stato": p.status,
            "data": data,
            "ora": ora,
            "durata_ore": p.duration_hours,
            # Offset UTC esplicito: consente al frontend di stabilire se la
            # sessione è passata senza reinterpretare le stringhe formattate.
            "start_time_iso": p.slot.start_time.replace(tzinfo=timezone.utc).isoformat()
        })
    return risultato


def get_or_create_user(db: Session, user: UserCreate) -> User:
    """Restituisce l'utente con questa email, creandolo se non esiste.

    L'unicità dell'email impedirebbe comunque un secondo inserimento: il
    vincolo viene trasformato in un comportamento utile invece che in un
    errore. Condivisa con i form di richiesta contatto.
    """
    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        return existing

    db_user = User(
        nome=user.nome,
        email=user.email,
        telefono=user.telefono,
        categoria=user.categoria,
        discord_tag=user.discord_tag
    )
    # refresh rilegge i campi generati dal database (id, created_at).
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.post("/", response_model=UserIdResponse)
# Endpoint pubblico: il rate limit per IP impedisce la creazione massiva di
# utenti, e la risposta ridotta evita di rivelare il profilo di un cliente
# esistente a chi ne indovini l'email.
@limiter.limit("5/minute")
def create_user(request: Request, user: UserCreate, db: Session = Depends(get_db)):
    # `request` non è usato nel corpo, ma slowapi lo richiede in firma per
    # identificare il chiamante.
    return get_or_create_user(db, user)


@router.get("/pacchetti-attivi")
def get_pacchetti_attivi(studente: User = Depends(get_studente), db: Session = Depends(get_db)):
    """Pacchetti con crediti residui dello studente autenticato.

    L'identità viene dal token verificato, mai da un parametro della
    richiesta: accettare un'email dalla query string permetterebbe a
    chiunque la conosca di leggere i crediti altrui.
    """
    pacchetti = db.query(Package).filter(
        Package.user_id == studente.id,
        Package.sessioni_usate < Package.sessioni_totali
    ).all()

    return [
        {
            "id": p.id,
            "user_id": p.user_id,
            "nome": CATALOGO_PACCHETTI.get(p.tipo, {}).get("nome", p.tipo),
            "sessioni_totali": p.sessioni_totali,
            "sessioni_usate": p.sessioni_usate,
            "sessioni_residue": p.sessioni_totali - p.sessioni_usate,
            "durata_sessione_ore": p.durata_sessione_ore
        }
        for p in pacchetti
    ]
