"""Credenziali OAuth2 Google condivise da Gmail e Drive.

Le due integrazioni usano refresh token distinti ma la stessa procedura:
un token ottenuto una tantum autorizzando l'app dal browser, scambiato al
bisogno con un access token temporaneo.
"""

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

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
