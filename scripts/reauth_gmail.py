"""Ottiene un nuovo GMAIL_REFRESH_TOKEN tramite autorizzazione OAuth2.

    python scripts/reauth_gmail.py

Apre il browser per autorizzare l'app con l'account mittente, stampa il
nuovo token e propone di scriverlo nel .env locale. Va eseguito in locale:
richiede un browser e un intervento umano, quindi non è automatizzabile
lato server. Aggiorna solo l'ambiente locale — la variabile in produzione
va sostituita a mano dalla dashboard dell'hosting.

QUANDO RILANCIARLO
Casi eccezionali: token revocato, cambio dell'account mittente, oppure
l'alert Discord dell'healthcheck. Non più a cadenza regolare.

Perché prima serviva spesso: finché la schermata di consenso OAuth è
rimasta in stato "Testing", il refresh token scadeva dopo 7 giorni **a
prescindere da quanto l'app venisse usata** — non per inattività: il
2026-09-02 è scaduto pur essendo esercitato ogni giorno. La schermata è
stata portata "In production" il 2026-09-04 e i token rigenerati; la
conferma definitiva è un token ancora valido dopo l'11 settembre 2026
(STATO_PROGETTO.md, §9.1 voce 1).

Nota sullo scope: gmail.send è classificato **sensitive** da Google. Non
impedisce di pubblicare — l'app resta "In production / needs verification"
e al consenso compare l'avviso "app non verificata", da superare con
Avanzate -> Continua.
"""

import os
import sys

# La radice del progetto è la cartella superiore a scripts/: serve per
# trovare il .env indipendentemente dalla directory di lancio.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env_utils import aggiorna_env_locale as aggiorna_env_locale_helper

from dotenv import load_dotenv
load_dotenv(ENV_PATH)

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("Manca la libreria google-auth-oauthlib.")
    print("Installala con: pip install -r requirements.txt")
    sys.exit(1)

# Stesso scope minimo documentato in README.md — SOLO invio email, niente
# lettura della casella di posta: se qualcuno rubasse questo token potrebbe
# mandare email a nome del coach, ma non leggere la sua posta.
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("GMAIL_CLIENT_ID e/o GMAIL_CLIENT_SECRET mancanti nel .env.")
        print("Vanno presi da Google Cloud Console (vedi README.md, sezione \"Gmail API\", punto 3).")
        sys.exit(1)

    # Stessa struttura che Google Cloud Console farebbe scaricare come
    # "client_secret.json" per un client OAuth di tipo "App per computer" —
    # qui è scritta a mano invece di leggerla da un file, per non dover
    # gestire un secondo file di credenziali oltre al .env.
    client_config = {
        "installed": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"]
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)

    print("Si apre il browser per l'autorizzazione — accedi con l'account Gmail del coach e autorizza l'accesso.")
    # run_local_server apre un piccolo server temporaneo sulla macchina
    # locale SOLO per ricevere il redirect di Google a fine autorizzazione
    # (porta 0 = scelta automatica di una porta libera) — si chiude da solo
    # subito dopo.
    credenziali = flow.run_local_server(port=0)

    nuovo_token = credenziali.refresh_token
    if not nuovo_token:
        print("Google non ha restituito un refresh token.")
        print("Probabile causa: questo account ha già un'autorizzazione attiva per questa stessa app.")
        print("Vai su https://myaccount.google.com/permissions, rimuovi l'accesso dell'app, e riprova.")
        sys.exit(1)

    print("\nNuovo GMAIL_REFRESH_TOKEN ottenuto:")
    print(nuovo_token)

    risposta = input("\nAggiornarlo subito nel .env locale? [s/N] ").strip().lower()
    if risposta == "s":
        aggiorna_env_locale(nuovo_token)
    else:
        print("Nessuna modifica al .env locale.")

    print(
        "\nRicordati di aggiornare GMAIL_REFRESH_TOKEN anche su Railway "
        "(Dashboard del progetto → Variables) — questo script aggiorna SOLO "
        "il .env locale, mai l'ambiente di produzione."
    )


def aggiorna_env_locale(nuovo_token: str):
    aggiorna_env_locale_helper(ENV_PATH, "GMAIL_REFRESH_TOKEN", nuovo_token)


if __name__ == "__main__":
    main()
