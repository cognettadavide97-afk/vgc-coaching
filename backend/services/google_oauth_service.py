"""Credenziali Google condivise, e la sonda che ne verifica la salute.

Gmail e Drive usano refresh token distinti ma la stessa procedura: un
token ottenuto una tantum autorizzando l'app dal browser, scambiato al
bisogno con un access token temporaneo. Calendar usa invece un service
account, con una chiave privata al posto del refresh token.

Le tre credenziali si costruiscono in modo diverso ma **si rompono allo
stesso modo**, e si verificano con la stessa identica operazione: per
questo la sonda vive qui, una volta sola, e non tre volte nei rispettivi
servizi.
"""

import logging

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)

# Cache per refresh token: l'access token ottenuto dura circa un'ora, e
# senza cache verrebbe richiesto a Google a ogni singola email o backup.
_credenziali_cache: dict[str, Credentials] = {}


def credenziali_oauth_google(refresh_token: str, client_id: str, client_secret: str) -> Credentials:
    """Restituisce credenziali con un access token valido.

    `client_id`/`client_secret` identificano l'applicazione registrata su
    Google Cloud; `refresh_token` identifica l'account che l'ha autorizzata
    ed è quindi la chiave giusta per la cache.
    """
    credenziali = _credenziali_cache.get(refresh_token)
    if credenziali is None:
        credenziali = Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token",
        )
        _credenziali_cache[refresh_token] = credenziali

    if not credenziali.valid:
        credenziali.refresh(Request())

    return credenziali


def verifica_credenziali_google(nome: str, costruisci_credenziali) -> bool:
    """Verifica che una credenziale Google sia ancora spendibile.

    `costruisci_credenziali` è una funzione senza argomenti che restituisce
    l'oggetto credenziali da provare: il chiamante sa come costruire le
    proprie, questa funzione sa solo come metterle alla prova. È ciò che
    permette a un'unica sonda di coprire i due refresh token (Gmail, Drive)
    e il service account di Calendar, che si costruiscono in tre modi
    diversi.

    La prova è lo **scambio con un access token**, cioè esattamente
    l'operazione che fallisce quando una credenziale scade o viene
    revocata: il guasto che questo controllo esiste per intercettare.

    Non interroga nessuna API applicativa, e non è un dettaglio. Lo scope
    concesso a Gmail è `gmail.send`, che autorizza a spedire e a
    nient'altro: una lettura di prova — `users.getProfile()`, che la sonda
    Gmail usava fino al 2026-09-04 — risponde 403 "insufficient
    authentication scopes" anche con credenziali perfettamente sane, quindi
    come sonda mentiva. Il refresh non ha quel problema, perché non dipende
    da nessuno scope: vale per tutte e tre le credenziali.

    Il `refresh()` esplicito serve a non fidarsi della cache qui sopra: un
    access token ancora fresco proverebbe solo che il controllo precedente
    era andato bene.

    Restituisce l'esito invece di sollevare, così un fallimento non
    interrompe lo scheduler che la richiama.
    """
    try:
        credenziali = costruisci_credenziali()
        credenziali.refresh(Request())
        return credenziali.token is not None
    except Exception:
        logger.exception("Controllo credenziali %s fallito", nome)
        return False
