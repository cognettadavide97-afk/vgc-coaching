# Questo file implementa il login "Accedi con Discord" — un flusso chiamato
# OAuth2 "Authorization Code". Vale la pena capirlo passo passo perché è lo
# STESSO identico meccanismo usato da "Accedi con Google", "Accedi con
# GitHub" e praticamente ogni pulsante di login di terze parti che vedi in
# giro. L'idea di fondo: il nostro sito non vede MAI la password
# dell'utente su Discord — è Discord stesso a occuparsi del login, e alla
# fine ci manda solo un "permesso" limitato per sapere chi è quella persona.

import os
import requests
from urllib.parse import urlencode
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.users import User
from backend.services.auth_service import crea_token_studente

router = APIRouter(prefix="/auth/discord", tags=["Discord Auth"])

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_OAUTH_REDIRECT_URI = os.getenv("DISCORD_OAUTH_REDIRECT_URI")

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
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify email",
        "prompt": "consent"
    }
    # urlencode(params) trasforma il dizionario in una stringa di query
    # tipo "client_id=123&redirect_uri=...&scope=identify+email" — con i
    # caratteri speciali "escapati" correttamente per essere validi in un
    # URL (es. spazi diventano %20 o +). RedirectResponse dice al browser
    # "vai su questo altro indirizzo", con un normale redirect HTTP (lo
    # stesso meccanismo che usi quando clicchi un link che ti porta altrove).
    return RedirectResponse(f"{DISCORD_AUTHORIZE_URL}?{urlencode(params)}")


@router.get("/callback")
def discord_callback(code: str = None, error: str = None, db: Session = Depends(get_db)):
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
    except Exception as e:
        print(f"Errore OAuth Discord: {e}")
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
    user = db.query(User).filter(User.discord_id == discord_id).first()
    if not user:
        user = db.query(User).filter(User.email == email).first()

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
    # API. Lo passiamo al frontend come parametro nell'URL di redirect: sarà
    # frontend/js/app.js a leggerlo dalla barra degli indirizzi e a salvarlo
    # (vedi initDiscordLogin in quel file).
    token = crea_token_studente(user.id, user.email)
    return RedirectResponse(f"/?student_token={token}")
