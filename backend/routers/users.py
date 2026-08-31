# Questo è il primo "router" che leggi, quindi spieghiamo per bene come
# funziona un router FastAPI — negli altri file di questa cartella troverai
# la stessa logica, con meno ripetizioni nei commenti.
#
# Un router raggruppa un insieme di "endpoint" (indirizzi web) legati tra
# loro da un prefisso comune. Ogni funzione qui sotto, decorata con
# @router.get(...) o @router.post(...), diventa raggiungibile da un browser
# o da fetch() nel frontend non appena main.py fa
# app.include_router(users.router) — prima di quel momento, questo file da
# solo non fa nulla di per sé, definisce solo del codice Python.

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

# APIRouter() crea "questo gruppo di indirizzi". prefix="/users" vuol dire
# che ogni endpoint qui sotto avrà "/users" davanti al proprio percorso —
# per esempio @router.get("/me") diventa davvero raggiungibile all'indirizzo
# "/users/me", non solo "/me".
router = APIRouter(prefix="/users", tags=["Users"])

# Nome del cookie httpOnly che porta il token studente — impostato dal
# server al login riuscito (vedi backend/routers/discord_auth.py), mai
# scritto né letto da JavaScript. Prima il token viaggiava nell'header
# "Authorization" (letto con OAuth2PasswordBearer, la stessa classe ancora
# usata per l'admin in backend/routers/admin/__init__.py) e il frontend lo
# teneva in localStorage —
# un bersaglio comodo per un eventuale script malevolo iniettato nella
# pagina (XSS): con un cookie httpOnly, nessuno script (nemmeno il nostro)
# può leggerlo, solo il browser lo allega da solo alle richieste verso
# questo stesso sito.
STUDENT_TOKEN_COOKIE = "student_token"


def get_studente_opzionale(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Questa funzione è una "dependency" — non è un endpoint, è un pezzo di
    logica riutilizzabile che altri endpoint richiedono con Depends(...).
    Nota come le dependency possono incatenarsi: questa funzione legge il
    cookie da sola (niente Depends aggiuntivo per farselo passare, a
    differenza di prima con OAuth2PasswordBearer), e a sua volta viene
    usata da get_studente() qui sotto — FastAPI risolve tutta la catena da
    solo, in ordine, prima di eseguire l'endpoint finale.
    """
    token = request.cookies.get(STUDENT_TOKEN_COOKIE)
    if not token:
        return None
    payload = verifica_token_studente(token)
    if not payload:
        return None
    return db.query(User).filter(User.id == payload["user_id"]).first()


def get_studente(studente: Optional[User] = Depends(get_studente_opzionale)) -> User:
    """
    Questa è la versione "obbligatoria": riusa get_studente_opzionale, ma se
    il risultato è None (nessun login), blocca la richiesta con un errore
    401 (Unauthorized) invece di lasciarla proseguire. È il pattern
    "dependency che ne richiama un'altra e aggiunge un controllo in più" —
    invece di riscrivere tutta la logica di lettura del token da capo.
    """
    if not studente:
        raise HTTPException(status_code=401, detail="Login required")
    return studente


# @router.get("/", ...) dice a FastAPI: "quando arriva una richiesta HTTP
# GET su /users/, esegui questa funzione". response_model=List[UserResponse]
# dice inoltre "il risultato deve avere la forma di una LISTA di
# UserResponse" — FastAPI userà questo per validare/formattare
# automaticamente l'output e per generare la documentazione su /docs.
#
# admin: str = Depends(get_admin) è quello che protegge questo endpoint:
# get_admin (definita in backend/routers/admin/__init__.py) controlla che ci sia un token JWT admin
# valido nell'header della richiesta, e se manca o non è valido blocca
# tutto PRIMA che il corpo della funzione venga eseguito. È così che il
# progetto protegge gli endpoint riservati, senza ripetere il controllo
# manualmente in ogni funzione.
@router.get("/", response_model=List[UserResponse])
def get_users(admin: str = Depends(get_admin), db: Session = Depends(get_db)):
    return db.query(User).all()


@router.get("/me", response_model=UserResponse)
def get_utente_corrente(studente: User = Depends(get_studente)):
    """Restituisce il profilo dello studente loggato via Discord, per precompilare il form."""
    # Qui "return studente" restituisce direttamente l'oggetto User (un
    # model SQLAlchemy) — FastAPI, grazie a response_model=UserResponse e a
    # from_attributes=True nello schema (vedi backend/schemas/users.py),
    # sa da solo come trasformarlo nel JSON corretto da mandare al client.
    return studente


@router.get("/me/prenotazioni")
def get_prenotazioni_studente(
    studente: User = Depends(get_studente),
    db: Session = Depends(get_db)
):
    """Storico prenotazioni dello studente loggato via Discord, più recenti prima."""
    # .join(Booking.slot) unisce le tabelle bookings e slots nella stessa
    # query (ci serve per poter ordinare per Slot.start_time, un campo che
    # sta sull'altra tabella). .order_by(Slot.start_time.desc()) ordina dal
    # più recente al più vecchio ("desc" = decrescente). Nota: passiamo la
    # relationship (Booking.slot), non solo "Slot" — da quando Booking ha
    # DUE colonne che puntano a slots (slot_id e slot_id_secondario, vedi
    # backend/models/booking.py), un semplice ".join(Slot)" non saprebbe più
    # quale delle due usare e solleverebbe un errore di ambiguità.
    # contains_eager(Booking.slot): il .join(Booking.slot) qui sopra serve
    # già a ordinare — senza dirlo esplicitamente a SQLAlchemy, il ciclo
    # sotto (p.slot.start_time, due volte per ogni prenotazione) rifarebbe
    # una query separata per ogni Slot invece di riusare quello già preso
    # col JOIN.
    prenotazioni = db.query(Booking).join(Booking.slot).options(
        contains_eager(Booking.slot)
    ).filter(
        Booking.user_id == studente.id
    ).order_by(Slot.start_time.desc()).all()

    # Qui, invece di restituire direttamente oggetti Booking, costruiamo a
    # mano una lista di dizionari con solo i campi che servono al frontend
    # (e già formattati in modo leggibile, es. la data). Questo endpoint
    # non usa un response_model Pydantic — FastAPI converte comunque questa
    # lista in JSON automaticamente, ma senza la validazione/documentazione
    # extra che avresti con uno schema dedicato.
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
            # ISO con offset UTC esplicito (stesso pattern di SlotResponse in
            # backend/schemas/slots.py), così il frontend può confrontare in
            # modo affidabile "è già passata?" senza dover reinterpretare le
            # stringhe già formattate "data"/"ora" sopra — serve al bottone
            # di cancellazione self-service, vedi frontend/js/app.js.
            "start_time_iso": p.slot.start_time.replace(tzinfo=timezone.utc).isoformat()
        })
    return risultato


def get_or_create_user(db: Session, user: UserCreate) -> User:
    """
    Pattern "get or create" (prendi se esiste, altrimenti crea): dato che
    email è unique nel database (vedi backend/models/users.py), non
    possiamo comunque creare un secondo utente con la stessa email — invece
    di far fallire la richiesta con un errore, la trasformiamo in un
    comportamento utile: "se questo studente ha già prenotato in passato,
    ritrovalo invece di dare errore". Riusata sia da POST /users/ sia dal
    form di richiesta consulenza gratuita (backend/routers/consulenza.py).
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
    # Queste tre righe sono il pattern standard di SQLAlchemy per salvare
    # qualcosa di nuovo:
    # db.add(...)     → "prepara" l'inserimento (non ancora salvato)
    # db.commit()      → salva DAVVERO nel database
    # db.refresh(...)  → rilegge l'oggetto dal database, per aggiornare i
    #                    campi che il database stesso ha generato (qui:
    #                    l'id assegnato automaticamente, e created_at)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.post("/", response_model=UserIdResponse)
# @limiter.limit("5/minute") è un secondo decoratore sullo stesso endpoint:
# applica la protezione anti-abuso vista in backend/rate_limit.py,
# impedendo che lo stesso indirizzo IP chiami questo endpoint più di 5
# volte al minuto — impedisce a un bot di creare migliaia di utenti falsi.
#
# response_model=UserIdResponse (non UserResponse): vedi il commento su
# UserIdResponse in backend/schemas/users.py — questo endpoint è "get or
# create" pubblico, quindi non deve rivelare il profilo di un cliente
# esistente a chiunque ne indovini l'email.
@limiter.limit("5/minute")
def create_user(request: Request, user: UserCreate, db: Session = Depends(get_db)):
    # request: Request è un parametro che slowapi richiede per poter
    # identificare da dove arriva la richiesta (il suo indirizzo IP) — non
    # lo usiamo direttamente nel corpo della funzione, ma deve essere
    # presente perché il decoratore @limiter.limit funzioni.
    return get_or_create_user(db, user)


@router.get("/pacchetti-attivi")
def get_pacchetti_attivi(studente: User = Depends(get_studente), db: Session = Depends(get_db)):
    """
    Pacchetti con crediti residui dello studente loggato. Fino al fix di
    sicurezza del 2026-08-25 questo endpoint era pubblico e prendeva
    un'email dalla query string — chiunque conoscesse l'email di un
    cliente poteva scoprire quanti crediti aveva ancora, senza nessuna
    prova di essere davvero lui (vedi il commento su "if not studente" in
    create_booking, backend/routers/booking.py, che usa esattamente questo
    endpoint per proporre "usa pacchetto" in UI — ma solo a chi è già
    loggato con Discord, vedi controllaPacchettoAttivo in
    frontend/js/app.js). Ora l'identità arriva dal token verificato dal
    server (get_studente), non da un parametro che chiunque può scrivere
    nell'URL.
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
