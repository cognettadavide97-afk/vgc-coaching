"""Login opzionale via Discord (OAuth2 Authorization Code).

L'applicazione non vede mai le credenziali dell'utente: Discord gestisce
l'autenticazione e restituisce un codice temporaneo, che viene scambiato
lato server per un access token con cui leggere identità ed email.

Il login resta facoltativo: la prenotazione come ospite è sempre
disponibile. Serve per usare i pacchetti, consultare lo storico e
cancellare le proprie prenotazioni.
"""

import os
import secrets
import logging
import requests
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.users import User
from backend.services.auth_service import crea_token_studente, EXPIRE_MINUTES
from backend.routers.users import STUDENT_TOKEN_COOKIE

# Cookie che trasporta il valore anti-CSRF fra /login e /callback.
STATE_COOKIE = "discord_oauth_state"

router = APIRouter(prefix="/auth/discord", tags=["Discord Auth"])
logger = logging.getLogger(__name__)

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_OAUTH_REDIRECT_URI = os.getenv("DISCORD_OAUTH_REDIRECT_URI")

# Determina se marcare i cookie come Secure. Non è deducibile da
# request.url.scheme: l'HTTPS è terminato da un proxy a monte, quindi
# all'applicazione la richiesta arriva sempre come HTTP. Il redirect URI è
# un segnale d'ambiente già affidabile, perché in produzione deve
# comunque essere https.
_IS_PRODUZIONE = (DISCORD_OAUTH_REDIRECT_URI or "").startswith("https://")

DISCORD_AUTHORIZE_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_USER_URL = "https://discord.com/api/users/@me"


@router.get("/login")
def discord_login():
    """Avvia il flusso OAuth2 reindirizzando l'utente su Discord.

    Lo scope richiesto è il minimo necessario a identificare l'utente.
    """
    # Valore anti-CSRF: viene inviato a Discord e salvato in un cookie. Il
    # callback accetta solo se i due coincidono. Senza, un attaccante
    # potrebbe iniettare un proprio codice valido nel browser della
    # vittima e farle usare il proprio account Discord.
    state = secrets.token_urlsafe(32)

    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify email",
        "prompt": "consent",
        "state": state
    }
    response = RedirectResponse(f"{DISCORD_AUTHORIZE_URL}?{urlencode(params)}")
    # samesite="lax" e non "strict": con "strict" il browser non
    # rimanderebbe il cookie al ritorno da Discord, che è una navigazione
    # cross-site, vanificando la protezione. La scadenza breve limita la
    # finestra utile del valore.
    response.set_cookie(
        STATE_COOKIE, state,
        httponly=True, secure=_IS_PRODUZIONE, samesite="lax", max_age=600
    )
    return response


@router.get("/callback")
def discord_callback(request: Request, code: str = None, error: str = None, state: str = None, db: Session = Depends(get_db)):
    """Completa il login: scambia il codice, identifica l'utente, apre la sessione.

    Chiamato da Discord dopo il consenso. In caso di rifiuto o errore
    reindirizza alla pagina pubblica con un parametro che il frontend
    traduce in un messaggio.
    """
    if error or not code:
        return RedirectResponse("/?discord_error=1")

    # Verifica anti-CSRF: lo state restituito deve coincidere con quello
    # salvato nel cookie. Assenza o mancata corrispondenza indicano una
    # richiesta che non è passata da /login su questo browser.
    cookie_state = request.cookies.get(STATE_COOKIE)
    if not state or not cookie_state or not secrets.compare_digest(state, cookie_state):
        response = RedirectResponse("/?discord_error=1")
        response.delete_cookie(STATE_COOKIE)
        return response

    try:
        # Scambio del codice monouso con un access token. Richiede il
        # client_secret, che resta lato server e non transita mai dal
        # browser.
        token_res = requests.post(
            DISCORD_TOKEN_URL,
            data={
                "client_id": DISCORD_CLIENT_ID,
                "client_secret": DISCORD_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": DISCORD_OAUTH_REDIRECT_URI
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10
        )
        token_res.raise_for_status()
        access_token = token_res.json()["access_token"]

        # Recupero del profilo con l'access token appena ottenuto.
        user_res = requests.get(
            DISCORD_USER_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10
        )
        user_res.raise_for_status()
        discord_user = user_res.json()
    except Exception:
        logger.exception("Errore OAuth Discord")
        return RedirectResponse("/?discord_error=1")

    # "id" è l'identificativo permanente; il tag testuale è modificabile
    # dall'utente e non va usato come identità.
    discord_id = discord_user.get("id")
    email = discord_user.get("email")
    username = discord_user.get("username")
    # Gli account storici hanno ancora il discriminator numerico, quelli
    # nuovi no (vale "0"): il tag va composto di conseguenza.
    discriminator = discord_user.get("discriminator", "0")
    discord_tag = username if discriminator == "0" else f"{username}#{discriminator}"

    if not email or not discord_id:
        return RedirectResponse("/?discord_error=1")

    # Ricerca per discord_id, con fallback sull'email per chi aveva già
    # prenotato come ospite. Il fallback collega un account Discord a
    # un'identità esistente, quindi è ammesso solo se Discord dichiara
    # l'email verificata: altrimenti basterebbe aggiungere al proprio
    # account l'email di un cliente per ottenerne la sessione.
    user = db.query(User).filter(User.discord_id == discord_id).first()
    if not user:
        utente_per_email = db.query(User).filter(User.email == email).first()
        if utente_per_email:
            if not discord_user.get("verified"):
                # Email non verificata e già appartenente a un altro utente:
                # non si può collegare né duplicare (vincolo di unicità),
                # quindi il login viene rifiutato.
                return RedirectResponse("/?discord_error=1")
            user = utente_per_email

    if user:
        # Collega l'account Discord all'utente esistente. Il tag inserito a
        # mano, se presente, non viene sovrascritto.
        user.discord_id = discord_id
        if not user.discord_tag:
            user.discord_tag = discord_tag
    else:
        user = User(nome=username, email=email, discord_id=discord_id, discord_tag=discord_tag)
        db.add(user)

    db.commit()
    db.refresh(user)

    # Da qui in avanti Discord non è più coinvolto: la sessione è retta da
    # un token JWT dell'applicazione, consegnato come cookie httpOnly e
    # quindi non leggibile da JavaScript.
    token = crea_token_studente(user.id, user.email)
    response = RedirectResponse("/")
    # Lo state è già stato verificato: il cookie non serve più.
    response.delete_cookie(STATE_COOKIE)
    response.set_cookie(
        STUDENT_TOKEN_COOKIE, token,
        httponly=True, secure=_IS_PRODUZIONE, samesite="lax",
        # Allineata alla validità del token contenuto.
        max_age=EXPIRE_MINUTES * 60
    )
    return response


@router.post("/logout")
def logout():
    """Chiude la sessione dello studente cancellandone il cookie.

    Serve un endpoint dedicato perché un cookie httpOnly non è
    cancellabile lato client.
    """
    response = JSONResponse({"message": "Logged out"})
    response.delete_cookie(STUDENT_TOKEN_COOKIE)
    return response
