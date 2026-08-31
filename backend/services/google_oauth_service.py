# Un'unica funzione, condivisa da email_service.py (Gmail) e
# backup_service.py (Drive): entrambi si autenticano con OAuth2 usando un
# refresh token ottenuto una tantum autorizzando l'app dal browser (vedi
# scripts/reauth_gmail.py e scripts/reauth_drive.py), scambiato per un
# access token temporaneo — mai una password permanente salvata da nessuna
# parte. Prima di questo file, lo stesso identico blocco (Credentials(...) +
# .refresh(Request())) era scritto tre volte in due file diversi: un bug fix
# o un cambio di token_uri avrebbe dovuto essere ripetuto in tre punti
# invece che uno solo.
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# Cache in memoria delle Credentials già ottenute, una per refresh_token
# (Gmail e Drive ne usano uno diverso a testa — vedi il commento su
# DRIVE_REFRESH_TOKEN in .env.example — quindi la chiave giusta è il
# refresh_token, non una singola variabile globale). Prima .refresh() veniva
# chiamata ad OGNI singola email/backup, anche quando l'access token
# ottenuto un attimo prima era ancora valido (dura circa un'ora): un giro
# HTTPS a Google in più, del tutto evitabile, ripetuto due volte per ogni
# prenotazione (email cliente + email admin). L'oggetto Credentials sa da
# solo dirci se è ancora valido (.valid) — lo riusiamo finché lo è, e lo
# aggiorniamo solo quando serve davvero.
_credenziali_cache: dict[str, Credentials] = {}


def credenziali_oauth_google(refresh_token: str, client_id: str, client_secret: str) -> Credentials:
    """
    Restituisce delle credenziali OAuth pronte all'uso (con un access token
    valido) per il refresh_token indicato — client_id/client_secret
    identificano LA NOSTRA app registrata su Google Cloud, refresh_token
    identifica invece l'account Google che ha autorizzato quella specifica
    app (mittente Gmail o proprietario della cartella Drive, a seconda del
    chiamante). Se in cache c'è già un access token valido per questo
    refresh_token lo restituisce direttamente, senza rifare la chiamata
    HTTPS a Google.
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
