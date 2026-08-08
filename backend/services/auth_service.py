# Questo file gestisce l'autenticazione: come si crea e si verifica un
# "token" che prova l'identità di chi sta facendo una richiesta, sia per il
# coach (pannello admin) sia per uno studente loggato via Discord.
#
# Il concetto centrale è il JWT (JSON Web Token). Vale la pena capirlo bene
# perché lo ritroverai in moltissimi progetti web reali. Un JWT è una
# stringa tipo "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiJ9.abc123..." composta
# da tre parti separate da un punto:
#   1. un'intestazione (che algoritmo è stato usato per firmarlo)
#   2. un "payload" — un dizionario JSON con le informazioni vere e proprie
#      (in questo file: chi è l'utente, quando scade...)
#   3. una firma digitale, calcolata a partire dalle prime due parti PIÙ una
#      chiave segreta che solo il server conosce (SECRET_KEY)
#
# Il punto chiave: CHIUNQUE può leggere il payload di un JWT (è solo testo
# codificato, non cifrato — non nasconde nulla) ma SOLO chi conosce la
# chiave segreta può crearne uno con una firma valida, o verificare che una
# firma sia autentica. Per questo un JWT funziona come "documento
# d'identità": il server lo emette una volta (al login), e poi può fidarsi
# di ogni richiesta che lo presenta, senza dover ricontrollare la password
# ogni volta né tenere traccia delle sessioni attive da qualche parte.

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
    Genera un token JWT firmato con la SECRET_KEY per il pannello admin.
    Il token contiene il nome utente, un claim "type" (per non essere
    confuso con un token studente) e la scadenza.
    """
    # datetime.utcnow() + timedelta(...) calcola "tra EXPIRE_MINUTES minuti
    # da adesso" — questo istante finisce dentro al token stesso, così che
    # verificarlo più avanti non richieda nessuna informazione esterna
    # (nessuna riga in un database che dice "questa sessione è scaduta"):
    # il token "sa" da solo quando smette di essere valido.
    scadenza = datetime.utcnow() + timedelta(minutes=EXPIRE_MINUTES)

    # "dati" è il payload — le informazioni contenute nel token, leggibili
    # da chiunque lo decodifichi (ma non modificabili senza invalidare la
    # firma). I nomi "sub" ed "exp" non sono a caso: sono standard del
    # formato JWT ("sub" = subject/soggetto, "exp" = expiration/scadenza) —
    # jwt.decode() li riconosce e controlla automaticamente la scadenza.
    dati = {
        "sub": username,        # subject — chi è l'utente
        "type": "admin",        # distingue questo token da uno studente (vedi sotto)
        "exp": scadenza         # expiration — quando scade
    }
    # jwt.encode() è la funzione che davvero "firma" il token: prende il
    # payload, l'algoritmo e la chiave segreta, e restituisce la stringa
    # finale, pronta da mandare al client.
    token = jwt.encode(dati, SECRET_KEY, algorithm=ALGORITHM)
    return token


def crea_token_studente(user_id: int, email: str) -> str:
    """
    Genera un token JWT per uno studente loggato via Discord OAuth2.
    Strutturalmente diverso da un token admin (claim "type" diverso),
    così non può essere usato per accedere agli endpoint del pannello admin.
    """
    # ATTENZIONE, dettaglio di sicurezza importante: questa funzione e
    # crea_token() sopra sembrano quasi identiche, ma il campo "type" è
    # cruciale. Senza questa distinzione, un token emesso per uno studente
    # avrebbe la STESSA struttura di un token admin, e un utente malizioso
    # potrebbe provare a usare il proprio token studente per accedere agli
    # endpoint del pannello admin (che si fidano di qualunque token JWT
    # valido). Aggiungendo "type": "student" qui e "type": "admin" sopra,
    # e controllando questo campo in verifica_token()/verifica_token_studente()
    # più sotto, i due tipi di accesso restano completamente separati anche
    # se condividono la stessa chiave segreta e lo stesso meccanismo di firma.
    scadenza = datetime.utcnow() + timedelta(minutes=EXPIRE_MINUTES)
    dati = {
        "sub": email,
        "type": "student",
        "user_id": user_id,  # utile per ritrovare subito l'utente nel database, senza cercarlo per email
        "exp": scadenza
    }
    return jwt.encode(dati, SECRET_KEY, algorithm=ALGORITHM)


def _decodifica(token: str) -> dict | None:
    # Il nome inizia con "_" per convenzione Python: indica "funzione
    # privata, pensata per essere usata solo dentro questo file", anche se
    # tecnicamente nulla impedisce di importarla altrove (Python non ha un
    # vero "private" come altri linguaggi — è solo una convenzione che i
    # programmatori si impegnano a rispettare).
    try:
        # jwt.decode() fa il lavoro inverso di jwt.encode(): verifica che la
        # firma sia autentica (cioè che il token sia stato creato da questo
        # stesso server, con questa stessa SECRET_KEY) E che non sia scaduto
        # (controllando da solo il campo "exp"). Se una delle due cose non
        # va, solleva un'eccezione JWTError invece di restituire un payload.
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        # "except JWTError: return None" trasforma un errore in un semplice
        # "niente" — chi chiama questa funzione non deve preoccuparsi di
        # gestire eccezioni, gli basta controllare "if risultato is None".
        # Il tipo di ritorno "dict | None" nella firma della funzione
        # (sintassi moderna di Python, equivalente a Optional[dict]) rende
        # esplicito che può restituire "niente" in caso di problemi.
        return None


def verifica_token(token: str) -> str | None:
    """
    Verifica che il token sia un token ADMIN valido e non scaduto.
    Restituisce il nome utente se valido, None altrimenti
    (anche se il token è valido ma è di tipo "student").
    """
    payload = _decodifica(token)
    # Questo controllo è il cuore della separazione admin/studente descritta
    # sopra: anche se il token è tecnicamente valido (firma corretta, non
    # scaduto), viene comunque rifiutato se non ha "type": "admin".
    if not payload or payload.get("type") != "admin":
        return None
    return payload.get("sub")


def verifica_token_studente(token: str) -> dict | None:
    """
    Verifica che il token sia un token STUDENTE valido e non scaduto.
    Restituisce il payload (con user_id ed email) se valido, None altrimenti.
    """
    payload = _decodifica(token)
    if not payload or payload.get("type") != "student":
        return None
    return payload
