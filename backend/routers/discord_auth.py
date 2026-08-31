# Questo file implementa il login "Accedi con Discord" — un flusso chiamato
# OAuth2 "Authorization Code". Vale la pena capirlo passo passo perché è lo
# STESSO identico meccanismo usato da "Accedi con Google", "Accedi con
# GitHub" e praticamente ogni pulsante di login di terze parti che vedi in
# giro. L'idea di fondo: il nostro sito non vede MAI la password
# dell'utente su Discord — è Discord stesso a occuparsi del login, e alla
# fine ci manda solo un "permesso" limitato per sapere chi è quella persona.

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

# Nome del cookie usato per la protezione CSRF del login (vedi il
# commento su STATE in discord_login qui sotto).
STATE_COOKIE = "discord_oauth_state"

router = APIRouter(prefix="/auth/discord", tags=["Discord Auth"])
logger = logging.getLogger(__name__)

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_OAUTH_REDIRECT_URI = os.getenv("DISCORD_OAUTH_REDIRECT_URI")

# Decide se i cookie che impostiamo (stato OAuth e sessione studente) vanno
# marcati Secure (mandati solo su HTTPS). Non possiamo dedurlo da
# request.url.scheme: Railway termina l'HTTPS a un proxy davanti all'app,
# quindi dentro il processo la richiesta arriva sempre come HTTP semplice,
# a meno di configurare esplicitamente uvicorn per fidarsi degli header
# X-Forwarded-Proto (non fatto — vedi nixpacks.toml). Usiamo invece
# DISCORD_OAUTH_REDIRECT_URI, che il README impone già di aggiornare con
# il dominio reale in produzione (sempre https) mentre in locale resta
# "http://127.0.0.1:8000/..." — un segnale d'ambiente già corretto senza
# bisogno di una variabile in più.
_IS_PRODUZIONE = (DISCORD_OAUTH_REDIRECT_URI or "").startswith("https://")

# Questi tre indirizzi appartengono a Discord, non a noi — sono documentati
# sul loro sito per sviluppatori. Il nostro programma li chiama, non li
# implementa.
DISCORD_AUTHORIZE_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_USER_URL = "https://discord.com/api/users/@me"


@router.get("/login")
def discord_login():
    """
    Reindirizza lo studente alla pagina di autorizzazione Discord.
    Login sempre opzionale: il guest checkout resta disponibile senza passare da qui.
    """
    # STEP 1 del flusso OAuth2: mandiamo il browser dello studente su
    # Discord, con alcuni parametri nell'URL che dicono a Discord "chi sono
    # io" (client_id — identifica LA NOSTRA app, non lo studente) e "dove
    # rimandarmi indietro" (redirect_uri) dopo che l'utente ha dato il
    # consenso. scope="identify email" chiede solo il permesso di leggere
    # nome utente ed email — non chiediamo accesso a nient'altro.
    #
    # "state": protezione CSRF standard del flusso OAuth2 (senza, un
    # attaccante potrebbe iniettare un proprio "code" Discord valido nel
    # browser della vittima — vedi discord_callback — facendola
    # autenticare con l'account Discord DELL'ATTACCANTE, "login CSRF").
    # secrets.token_urlsafe genera un valore casuale imprevedibile; lo
    # mandiamo a Discord (tornerà indietro tale e quale nel redirect) E lo
    # salviamo in un cookie sul browser dello studente — discord_callback
    # accetta solo se i due valori coincidono, cosa che un sito esterno
    # non può falsificare (non può leggere né impostare i NOSTRI cookie).
    state = secrets.token_urlsafe(32)

    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify email",
        "prompt": "consent",
        "state": state
    }
    # urlencode(params) trasforma il dizionario in una stringa di query
    # tipo "client_id=123&redirect_uri=...&scope=identify+email" — con i
    # caratteri speciali "escapati" correttamente per essere validi in un
    # URL (es. spazi diventano %20 o +). RedirectResponse dice al browser
    # "vai su questo altro indirizzo", con un normale redirect HTTP (lo
    # stesso meccanismo che usi quando clicchi un link che ti porta altrove).
    response = RedirectResponse(f"{DISCORD_AUTHORIZE_URL}?{urlencode(params)}")
    # httponly=True: invisibile a JavaScript (niente da rubare via XSS).
    # samesite="lax": è il valore giusto per un cookie di redirect OAuth —
    # "strict" impedirebbe al browser di rimandarcelo indietro proprio
    # quando Discord reindirizza l'utente al nostro /callback (è una
    # navigazione "cross-site" dal punto di vista del browser), vanificando
    # la protezione; "lax" lo permette solo per navigazioni dirette come
    # questa, non per richieste in background da altri siti. max_age=600
    # (10 minuti): il tempo che uno studente impiega a fare login su
    # Discord è sempre molto meno — dopo, il cookie scade da solo.
    response.set_cookie(
        STATE_COOKIE, state,
        httponly=True, secure=_IS_PRODUZIONE, samesite="lax", max_age=600
    )
    return response


@router.get("/callback")
def discord_callback(request: Request, code: str = None, error: str = None, state: str = None, db: Session = Depends(get_db)):
    """
    Riceve il codice di autorizzazione da Discord, lo scambia per un
    access token, recupera identità ed email dello studente, trova o
    crea il suo User (per discord_id, poi per email) e lo rimanda al
    form pubblico con un token studente nell'URL.
    """
    # Questo endpoint è quello che Discord chiama DA SOLO (redirect_uri
    # configurato sopra), dopo che lo studente ha dato il consenso sul
    # sito di Discord. Se l'utente rifiuta, o qualcosa va storto, Discord
    # aggiunge "error" all'URL invece di "code" — in quel caso rimandiamo
    # subito alla pagina pubblica con un parametro di errore, che il
    # JavaScript del frontend (frontend/js/app.js) sa interpretare per
    # mostrare un messaggio.
    if error or not code:
        return RedirectResponse("/?discord_error=1")

    # Verifica CSRF (vedi il commento su "state" in discord_login): lo
    # "state" che Discord ci restituisce ora deve essere IDENTICO a quello
    # che avevamo salvato nel cookie prima di mandare l'utente su Discord.
    # Se manca, non combacia, o il cookie non c'è più (scaduto, o questa
    # richiesta non è mai passata da /login su questo stesso browser),
    # rifiutiamo: è esattamente lo scenario di un "code" iniettato da un
    # attaccante nel browser della vittima.
    cookie_state = request.cookies.get(STATE_COOKIE)
    if not state or not cookie_state or not secrets.compare_digest(state, cookie_state):
        response = RedirectResponse("/?discord_error=1")
        response.delete_cookie(STATE_COOKIE)
        return response

    try:
        # STEP 2: "code" è un codice temporaneo, usa-e-getta, che prova che
        # l'utente ha davvero appena dato il consenso. Da solo non basta per
        # sapere chi sia: dobbiamo scambiarlo con Discord per ottenere un
        # "access token" vero — e per farlo dobbiamo anche dimostrare di
        # essere davvero LA NOSTRA app, mandando anche il client_secret (la
        # password segreta della nostra app OAuth2, mai visibile al
        # browser dell'utente).
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

        # STEP 3: ora che abbiamo un access_token valido, lo usiamo per
        # chiedere a Discord "chi è questo utente?" — headers={"Authorization":
        # f"Bearer {access_token}"} è il modo standard di presentare un
        # token in una richiesta HTTP (lo stesso schema che il NOSTRO
        # frontend usa per parlare con NOI, vedi frontend/js/app.js).
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

    # discord_user è un dizionario con i dati che Discord ci ha restituito.
    # "id" è l'identificativo numerico permanente (vedi il commento su
    # discord_id in backend/models/users.py) — diverso dal "tag" testuale,
    # che l'utente può cambiare quando vuole.
    discord_id = discord_user.get("id")
    email = discord_user.get("email")
    username = discord_user.get("username")
    # Discord ha cambiato negli anni il proprio sistema di username: gli
    # account più vecchi hanno ancora un "discriminator" (le 4 cifre dopo
    # il cancelletto, tipo "Nome#1234"), quelli nuovi no (discriminator
    # vale "0"). Questa riga costruisce il tag "giusto" in entrambi i casi.
    discriminator = discord_user.get("discriminator", "0")
    discord_tag = username if discriminator == "0" else f"{username}#{discriminator}"

    if not email or not discord_id:
        return RedirectResponse("/?discord_error=1")

    # trova l'utente per discord_id (login successivo) o per email
    # (studente che aveva già prenotato via guest checkout con questa email)
    # — il fallback per email collega un account Discord a un utente
    # esistente, quindi va fatto SOLO se Discord garantisce che quell'email
    # appartiene davvero a chi sta facendo login (discord_user["verified"]).
    # Senza questo controllo, chiunque aggiunga l'email (non verificata) di
    # un altro cliente al proprio account Discord otterrebbe un cookie di
    # sessione legato all'identità di quel cliente — storico prenotazioni,
    # pacchetti residui inclusi.
    user = db.query(User).filter(User.discord_id == discord_id).first()
    if not user:
        utente_per_email = db.query(User).filter(User.email == email).first()
        if utente_per_email:
            if not discord_user.get("verified"):
                # L'email appartiene già a un altro utente ma Discord non
                # garantisce che sia davvero sua: non ci colleghiamo (furto
                # di identità) e non possiamo nemmeno creare un nuovo utente
                # con la stessa email (colonna UNIQUE) — rifiutiamo il login.
                return RedirectResponse("/?discord_error=1")
            user = utente_per_email

    if user:
        # Utente già esistente: aggiorniamo il suo discord_id (utile se
        # aveva prenotato come ospite e questo è il primo login) e, solo se
        # non aveva già un tag testuale scritto a mano, lo popoliamo con
        # quello vero di Discord.
        user.discord_id = discord_id
        if not user.discord_tag:
            user.discord_tag = discord_tag
    else:
        # Prima volta in assoluto: creiamo un nuovo utente con i dati presi
        # da Discord.
        user = User(nome=username, email=email, discord_id=discord_id, discord_tag=discord_tag)
        db.add(user)

    db.commit()
    db.refresh(user)

    # STEP 4, finale: creiamo il NOSTRO token JWT (vedi
    # backend/services/auth_service.py) — da qui in poi Discord non c'entra
    # più nulla, lo studente userà questo token per parlare con la nostra
    # API. A differenza di prima, non lo passiamo più al frontend nell'URL
    # di redirect: lo impostiamo direttamente come cookie httpOnly, quindi
    # invisibile e non manipolabile da JavaScript (vedi il commento su
    # STUDENT_TOKEN_COOKIE in backend/routers/users.py sul perché è più
    # sicuro di localStorage). Il browser lo allegherà da solo ad ogni
    # richiesta successiva verso questo stesso sito.
    token = crea_token_studente(user.id, user.email)
    response = RedirectResponse("/")
    # Il cookie di stato ha fatto il suo lavoro (già verificato sopra) — lo
    # rimuoviamo, non serve tenerlo dopo un login riuscito.
    response.delete_cookie(STATE_COOKIE)
    response.set_cookie(
        STUDENT_TOKEN_COOKIE, token,
        httponly=True, secure=_IS_PRODUZIONE, samesite="lax",
        # Stessa durata del token JWT stesso (vedi EXPIRE_MINUTES in
        # auth_service.py): non ha senso tenere il cookie più a lungo di
        # quanto il token al suo interno resti valido.
        max_age=EXPIRE_MINUTES * 60
    )
    return response


@router.post("/logout")
def logout():
    """
    Cancella il cookie di sessione dello studente. Un cookie httpOnly non
    è cancellabile da JavaScript (vedi frontend/js/app.js, logoutStudent)
    — serve chiedere esplicitamente al server di farlo, con una richiesta
    dedicata come questa.
    """
    response = JSONResponse({"message": "Logged out"})
    response.delete_cookie(STUDENT_TOKEN_COOKIE)
    return response
