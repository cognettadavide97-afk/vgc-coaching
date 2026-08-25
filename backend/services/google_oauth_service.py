# Un'unica funzione, condivisa da email_service.py (Gmail) e
# backup_service.py (Drive): entrambi si autenticano con OAuth2 usando un
# refresh token ottenuto una tantum autorizzando l'app dal browser (vedi
# scripts/reauth_gmail.py e scripts/reauth_drive.py), scambiato ad ogni
# chiamata vera per un access token temporaneo — mai una password
# permanente salvata da nessuna parte. Prima di questo file, lo stesso
# identico blocco (Credentials(...) + .refresh(Request())) era scritto tre
# volte in due file diversi: un bug fix o un cambio di token_uri avrebbe
# dovuto essere ripetuto in tre punti invece che uno solo.
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request


def credenziali_oauth_google(refresh_token: str, client_id: str, client_secret: str) -> Credentials:
    """
    Scambia un refresh token per delle credenziali OAuth pronte all'uso
    (già "aggiornate" con un access token valido) — client_id/client_secret
    identificano LA NOSTRA app registrata su Google Cloud, refresh_token
    identifica invece l'account Google che ha autorizzato quella specifica
    app (mittente Gmail o proprietario della cartella Drive, a seconda del
    chiamante).
    """
    credenziali = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
    )
    credenziali.refresh(Request())
    return credenziali
