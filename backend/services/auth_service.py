import os
from datetime import datetime, timedelta
from jose import JWTError, jwt
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", 480))

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

def verifica_credenziali(username: str, password: str) -> bool:
    """
    Controlla che username e password corrispondano
    a quelle salvate nel .env
    """
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD

def crea_token(username: str) -> str:
    """
    Genera un token JWT firmato con la SECRET_KEY.
    Il token contiene il nome utente e la scadenza.
    """
    scadenza = datetime.utcnow() + timedelta(minutes=EXPIRE_MINUTES)
    dati = {
        "sub": username,        # subject — chi è l'utente
        "exp": scadenza         # expiration — quando scade
    }
    token = jwt.encode(dati, SECRET_KEY, algorithm=ALGORITHM)
    return token

def verifica_token(token: str) -> str | None:
    """
    Verifica che il token sia valido e non scaduto.
    Restituisce il nome utente se valido, None altrimenti.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        return username
    except JWTError:
        return None