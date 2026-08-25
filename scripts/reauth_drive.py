# Script "una tantum" per ottenere DRIVE_REFRESH_TOKEN, usato dal backup
# automatico del database (vedi backend/services/backup_service.py). Va
# eseguito A MANO dal computer del coach, MAI su Railway: apre il browser
# e chiede di autorizzare l'app dal VERO account Google del coach — non un
# service account (vedi il commento in cima a backup_service.py sul perché:
# un service account non ha quota di archiviazione propria su Drive, un
# problema scoperto solo provando un upload reale, non a priori).
#
# Stesso identico schema di scripts/reauth_gmail.py (stesso client OAuth,
# GMAIL_CLIENT_ID/GMAIL_CLIENT_SECRET — non serve crearne uno nuovo, basta
# aggiungere lo scope Drive alla stessa schermata di consenso su Google
# Cloud Console), ma produce un token DIVERSO e SEPARATO
# (DRIVE_REFRESH_TOKEN, non GMAIL_REFRESH_TOKEN): tenerli separati vuol
# dire che se uno dei due scade o viene revocato, l'altro continua a
# funzionare indipendentemente.
#
# COME SI USA
#   python scripts/reauth_drive.py
# Si apre il browser: accedi con IL TUO account Google normale (quello a
# cui appartiene la cartella di backup su Drive) e autorizza. Lo script poi:
#   1. stampa il nuovo refresh token
#   2. chiede se aggiornarlo subito nel .env locale
#   3. ricorda di aggiornare la stessa variabile su Railway — quello NON
#      lo fa questo script, va fatto a mano dalla dashboard Railway.

import os
import sys

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

# drive.file, non "drive" pieno: l'app può leggere/scrivere SOLO i file che
# crea lei stessa, mai l'intero Drive del coach — principio di minimo
# privilegio, stesso motivo per cui lo scope Gmail è solo "gmail.send".
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("GMAIL_CLIENT_ID e/o GMAIL_CLIENT_SECRET mancanti nel .env.")
        print("Sono lo stesso client OAuth già usato per Gmail (vedi README.md, sezione \"Gmail API\").")
        sys.exit(1)

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

    print("Si apre il browser per l'autorizzazione — accedi con il TUO account Google (quello proprietario della cartella di backup) e autorizza l'accesso.")
    credenziali = flow.run_local_server(port=0)

    nuovo_token = credenziali.refresh_token
    if not nuovo_token:
        print("Google non ha restituito un refresh token.")
        print("Probabile causa: questo account ha già un'autorizzazione attiva per questa stessa app.")
        print("Vai su https://myaccount.google.com/permissions, rimuovi l'accesso dell'app, e riprova.")
        sys.exit(1)

    print("\nNuovo DRIVE_REFRESH_TOKEN ottenuto:")
    print(nuovo_token)

    risposta = input("\nAggiornarlo subito nel .env locale? [s/N] ").strip().lower()
    if risposta == "s":
        aggiorna_env_locale(nuovo_token)
    else:
        print("Nessuna modifica al .env locale.")

    print(
        "\nRicordati di aggiungere/aggiornare DRIVE_REFRESH_TOKEN anche su "
        "Railway (Dashboard del progetto → Variables) — questo script "
        "aggiorna SOLO il .env locale, mai l'ambiente di produzione."
    )


def aggiorna_env_locale(nuovo_token: str):
    aggiorna_env_locale_helper(ENV_PATH, "DRIVE_REFRESH_TOKEN", nuovo_token)


if __name__ == "__main__":
    main()
