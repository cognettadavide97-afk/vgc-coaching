"""Pannello di amministrazione: autenticazione, login e composizione.

Il pacchetto è diviso per area (dashboard, prenotazioni, clienti,
disponibilità, pacchetti, recensioni) invece di essere un unico modulo da
oltre mille righe. Questo file definisce l'autenticazione condivisa e
l'endpoint di login, poi assembla i sotto-router in un router unico.

`get_admin` è importato anche da moduli esterni al pacchetto: resta
esposto qui, e spostarlo altrove romperebbe quegli import.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from backend.services.auth_service import verifica_credenziali, crea_token, verifica_token
from backend.rate_limit import limiter

router = APIRouter(prefix="/admin", tags=["Admin"])

# Indica a FastAPI di cercare il token nell'header Authorization.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/login")


def get_admin(token: str = Depends(oauth2_scheme)):
    """Dependency che protegge gli endpoint di amministrazione.

    Presente nella firma di ogni endpoint del pacchetto tranne il login.
    Se il token manca o non è valido l'endpoint non viene mai eseguito e
    la richiesta termina con 401.
    """
    username = verifica_token(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token non valido o scaduto",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return username


@router.post("/login")
# Limite per IP contro i tentativi di forza bruta sulle credenziali.
@limiter.limit("5/minute")
def login(request: Request, form: OAuth2PasswordRequestForm = Depends()):
    """Autentica l'amministratore e restituisce un token JWT.

    Riceve le credenziali in formato form-urlencoded, non JSON: è il
    formato previsto da `OAuth2PasswordRequestForm`.
    """
    if not verifica_credenziali(form.username, form.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide"
        )
    token = crea_token(form.username)
    return {"access_token": token, "token_type": "bearer"}


# Import in fondo, e non in cima, perché ogni sotto-router importa
# `get_admin` da questo modulo: deve essere già definito quando vengono
# caricati. Spostarli in cima produce un import circolare.
from backend.routers.admin import dashboard, bookings, clients, availability, packages, reviews

router.include_router(dashboard.router)
router.include_router(bookings.router)
router.include_router(clients.router)
router.include_router(availability.router)
router.include_router(packages.router)
router.include_router(reviews.router)
