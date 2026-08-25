# Il pannello admin è diviso in più file per dominio (dashboard,
# prenotazioni, clienti, disponibilità, pacchetti, recensioni) invece di un
# unico file da oltre 1000 righe (backend/routers/admin.py, com'era prima
# — un solo file per login, dashboard, analytics, prenotazioni, clienti,
# slot, regole ricorrenti, blocchi eccezionali, pacchetti, recensioni,
# export CSV, tutti insieme) — più facile da aprire, leggere e modificare
# senza incappare in conflitti quando si lavora su parti diverse dello
# stesso pannello.
#
# Questo file (__init__.py) è il punto di ingresso del pacchetto: definisce
# l'autenticazione admin condivisa da TUTTI i sotto-router qui sotto
# (get_admin), l'endpoint di login, e assembla i sotto-router in un unico
# "router" — backend/main.py continua a importare questo pacchetto
# esattamente come importava prima il singolo file
# ("import backend.routers.admin as admin" e "app.include_router(admin.router)"),
# senza nessuna modifica lì.
#
# get_admin è importato da vari altri file del progetto AL DI FUORI di
# questo pacchetto (backend/routers/booking.py, backend/routers/users.py,
# backend/routers/slots.py) con "from backend.routers.admin import
# get_admin" — quella riga continua a funzionare identica: un pacchetto
# Python espone tramite il proprio __init__.py esattamente come farebbe un
# modulo singolo, chi lo importa da fuori non vede alcuna differenza.

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from backend.services.auth_service import verifica_credenziali, crea_token, verifica_token
from backend.rate_limit import limiter

router = APIRouter(prefix="/admin", tags=["Admin"])

# questo schema dice a FastAPI dove trovare il token
# nelle richieste HTTP — cercalo nell'header Authorization
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/login")


# ─── DIPENDENZA: VERIFICA ADMIN ──────────────────────────────
# questa funzione viene chiamata automaticamente su ogni
# endpoint protetto — se il token non è valido blocca tutto
def get_admin(token: str = Depends(oauth2_scheme)):
    # Questa è LA dependency più importante del progetto: quasi ogni
    # funzione nei sotto-router di questo pacchetto ha
    # "admin: str = Depends(get_admin)" tra i parametri, ed è proprio
    # questo che rende quell'endpoint "riservato al coach". FastAPI, prima
    # di eseguire l'endpoint vero, esegue sempre get_admin(): se qui dentro
    # viene sollevata un'eccezione, l'endpoint non viene MAI raggiunto — il
    # client riceve direttamente l'errore 401.
    username = verifica_token(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token non valido o scaduto",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return username


# ─── LOGIN ───────────────────────────────────────────────────
@router.post("/login")
# @limiter.limit("5/minute") blocca chi prova troppe password in poco
# tempo dallo stesso IP — stessa protezione già usata sugli altri endpoint
# di scrittura pubblici (vedi backend/routers/users.py), qui applicata al
# login admin che prima ne era privo.
@limiter.limit("5/minute")
def login(request: Request, form: OAuth2PasswordRequestForm = Depends()):
    """
    Riceve username e password dal form di login.
    Se corretti restituisce un token JWT.
    """
    # OAuth2PasswordRequestForm è una classe "pronta" di FastAPI che sa
    # leggere da sola un login username+password mandato in un formato
    # standard (non JSON, ma "form-urlencoded" — lo stesso formato che
    # userebbe un normale form HTML). Usato con Depends() (senza
    # argomenti), FastAPI costruisce automaticamente l'oggetto "form" con
    # form.username e form.password già pronti.
    if not verifica_credenziali(form.username, form.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide"
        )
    token = crea_token(form.username)
    # Il client (frontend/js/admin.js) salverà questo access_token e lo
    # userà in ogni richiesta successiva — è l'inizio della "sessione"
    # admin, anche se tecnicamente non esiste nessuna sessione salvata sul
    # server: il token stesso, come spiegato in auth_service.py, contiene
    # tutto il necessario per verificarsi da solo.
    return {"access_token": token, "token_type": "bearer"}


# Importati QUI, DOPO aver definito router/get_admin sopra apposta: ogni
# sotto-router importa get_admin da questo stesso file
# ("from backend.routers.admin import get_admin"), quindi get_admin deve
# già esistere nel modulo quando quell'import viene eseguito — con un
# pacchetto Python questo funziona solo se l'ordine qui sotto è quello
# giusto (prima si definisce tutto quello che serve agli altri, poi si
# importano gli altri).
from backend.routers.admin import dashboard, bookings, clients, availability, packages, reviews

router.include_router(dashboard.router)
router.include_router(bookings.router)
router.include_router(clients.router)
router.include_router(availability.router)
router.include_router(packages.router)
router.include_router(reviews.router)
