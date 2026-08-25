# Script "una tantum" (o "quando serve", vedi sotto) per ottenere un nuovo
# GMAIL_REFRESH_TOKEN. Va eseguito A MANO dal computer del coach, MAI su
# Railway: apre il browser e chiede di autorizzare di nuovo l'app dal suo
# account Gmail — un passaggio che richiede un umano davanti a un browser,
# non automatizzabile lato server (vedi il commento in
# backend/services/email_service.py sul perché serve OAuth2 invece di una
# semplice password).
#
# QUANDO SERVE RILANCIARLO
# Finché la schermata di consenso OAuth del progetto Google Cloud resta in
# stato "Testing" (vedi README.md, sezione "Gmail API"), il refresh token
# scade dopo 7 giorni di INATTIVITÀ dell'app — con l'app usata tutti i
# giorni per mandare email questo di norma non capita, ma può succedere
# (es. dopo una pausa, o se Google lo revoca per altri motivi). Lo
# scheduler del progetto (controlla_credenziali_gmail in
# backend/scheduler.py) controlla automaticamente e avvisa su Discord
# quando succede — a quel punto, rilancia questo script.
#
# LA SOLUZIONE DEFINITIVA resta un'altra: portare la schermata di consenso
# OAuth da "Testing" a "In production" su Google Cloud Console (un'azione
# manuale, una tantum, che NON richiede la verifica completa dell'app per
# un solo scope non sensibile come gmail.send) — fatto quello, il refresh
# token smette di scadere per inattività e questo script (e il controllo
# automatico) diventano solo una rete di sicurezza, non una necessità
# periodica.
#
# COME SI USA
#   python scripts/reauth_gmail.py
# Si apre il browser: accedi con l'account Gmail mittente (EMAIL_MITTENTE
# nel .env) e autorizza. Lo script poi:
#   1. stampa il nuovo refresh token
#   2. chiede se aggiornarlo subito nel .env locale (comodo per continuare
#      a sviluppare/testare in locale)
#   3. ricorda di aggiornare la stessa variabile su Railway (produzione) —
#      quello NON lo fa questo script, va fatto a mano dalla dashboard
#      Railway, per non toccare l'ambiente di produzione senza conferma
#      esplicita.

import os
import sys

# La cartella del progetto è quella SOPRA "scripts/" — serve per trovare il
# file .env indipendentemente da dove viene lanciato lo script.
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
