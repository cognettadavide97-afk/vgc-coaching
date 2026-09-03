"""Autenticazione: verifica credenziali e gestione dei token JWT.

Emette due tipi di token, admin e studente, distinti da un claim `type`.
La distinzione è una misura di sicurezza, non organizzativa: senza, un
token studente sarebbe strutturalmente indistinguibile da uno admin e
verrebbe accettato dagli endpoint del pannello, che condividono la stessa
chiave di firma.
"""

import os
import bcrypt
from datetime import datetime, timedelta
from jose import JWTError, jwt
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", 480))

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
# Solo l'hash bcrypt della password, mai la password in chiaro: un .env
# esposto non rivela la credenziale.
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH")


def verifica_credenziali(username: str, password: str) -> bool:
    """Verifica le credenziali di accesso al pannello di amministrazione."""
    if username != ADMIN_USERNAME or not ADMIN_PASSWORD_HASH:
        return False
    # bcrypt.checkpw riapplica alla password ricevuta il sale contenuto
    # nell'hash salvato e confronta i risultati: l'hash non viene mai
    # invertito.
    return bcrypt.checkpw(password.encode("utf-8"), ADMIN_PASSWORD_HASH.encode("utf-8"))


def crea_token(username: str) -> str:
    """Emette un token JWT per il pannello di amministrazione."""
    # La scadenza viaggia dentro il token ("exp", claim standard verificato
    # da jwt.decode): non serve alcuno stato lato server per invalidarlo.
    # Di conseguenza un token non può essere revocato prima della scadenza.
    scadenza = datetime.utcnow() + timedelta(minutes=EXPIRE_MINUTES)
    dati = {
        "sub": username,
        "type": "admin",
        "exp": scadenza
    }
    token = jwt.encode(dati, SECRET_KEY, algorithm=ALGORITHM)
    return token


def crea_token_studente(user_id: int, email: str) -> str:
    """Emette un token JWT per uno studente autenticato via Discord.

    Il claim `type` vale "student": è ciò che impedisce di riutilizzarlo
    sugli endpoint di amministrazione.
    """
    scadenza = datetime.utcnow() + timedelta(minutes=EXPIRE_MINUTES)
    dati = {
        "sub": email,
        "type": "student",
        "user_id": user_id,  # evita di dover ricercare l'utente per email
        "exp": scadenza
    }
    return jwt.encode(dati, SECRET_KEY, algorithm=ALGORITHM)


def _decodifica(token: str) -> dict | None:
    """Decodifica e verifica firma e scadenza. None se il token non è valido."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        # L'eccezione diventa un valore di ritorno: i chiamanti fanno un
        # semplice controllo su None invece di gestire eccezioni.
        return None


def verifica_token(token: str) -> str | None:
    """Restituisce lo username se il token è un token admin valido.

    Un token studente valido viene comunque rifiutato.
    """
    payload = _decodifica(token)
    if not payload or payload.get("type") != "admin":
        return None
    return payload.get("sub")


def verifica_token_studente(token: str) -> dict | None:
    """Restituisce il payload se il token è un token studente valido.

    Un token admin valido viene comunque rifiutato.
    """
    payload = _decodifica(token)
    if not payload or payload.get("type") != "student":
        return None
    return payload
