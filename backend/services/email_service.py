# Questo file si occupa di UNA cosa sola: costruire e inviare le email
# dell'app (conferma prenotazione, promemoria, notifica al coach), usando
# il server SMTP di Gmail come "postino" — un programma normale non può
# "inviare email" da solo: ha bisogno di appoggiarsi al server di posta di
# qualcuno, in questo caso lo stesso account Gmail del coach (autenticato
# con una "password per le app", non la password normale dell'account).
# smtplib ed email.message sono moduli della libreria standard di Python:
# nessuna dipendenza esterna da installare per mandare email.
#
# Pattern che vedrai ripetuto in ogni funzione di questo file: costruire il
# contenuto, provare a inviarlo, e se qualcosa va storto stampare l'errore
# invece di far fallire tutta la richiesta. Guarda il commento dentro
# invia_conferma_cliente per il perché di questa scelta.

import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
EMAIL_MITTENTE = os.getenv("EMAIL_MITTENTE")
EMAIL_ADMIN = os.getenv("EMAIL_ADMIN")
COACH_DISCORD_TAG = os.getenv("COACH_DISCORD_TAG")
COACH_TELEGRAM_CONTACT = os.getenv("COACH_TELEGRAM_CONTACT")


# Funzione condivisa dalle tre email qui sotto: costruisce il messaggio
# (con una versione testuale semplice + quella HTML vera e propria, così i
# client di posta che non mostrano HTML hanno comunque un contenuto
# leggibile) e lo invia collegandosi al server SMTP di Gmail con
# STARTTLS (la connessione parte in chiaro e viene "promossa" a cifrata
# prima di inviare login e contenuto — è lo standard per la porta 587).
def _invia_via_gmail(destinatario: str, oggetto: str, corpo_html: str):
    messaggio = EmailMessage()
    messaggio["From"] = EMAIL_MITTENTE
    messaggio["To"] = destinatario
    messaggio["Subject"] = oggetto
    messaggio.set_content("Questa email richiede un client che supporta l'HTML per essere visualizzata correttamente.")
    messaggio.add_alternative(corpo_html, subtype="html")

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(EMAIL_MITTENTE, EMAIL_APP_PASSWORD)
        server.send_message(messaggio)


def invia_conferma_cliente(
    email_cliente: str,
    nome_cliente: str,
    data_slot: str,
    ora_slot: str,
    durata: int,
    prezzo: int
):
    prezzo_euro = prezzo / 100

    # Questa è una f-string multi-riga (le tre virgolette """ permettono a
    # una stringa di andare a capo). Ogni {qualcosa} dentro le graffe viene
    # sostituito con il valore vero della variabile — esattamente come
    # faresti con una f-string normale in una riga sola, solo che qui il
    # contenuto è codice HTML: il "corpo" dell'email, con tag <div>, <h1>,
    # <p>... Un client di posta (Gmail, Outlook...) sa interpretare HTML
    # dentro un'email e la mostra formattata, non come testo grezzo.
    #
    # {"e" if durata > 1 else ""} è un'espressione condizionale (l'"if" in
    # una riga sola, equivalente a scrivere "e" if durata > 1 else "")
    # dentro la f-string: serve solo per scrivere "1 ora" ma "2 ore" — una
    # piccola concordanza grammaticale automatica.
    corpo_email = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">

        <div style="background: #1a1a2e; padding: 2rem; text-align: center;">
            <h1 style="color: white; margin: 0;">VGC Coaching</h1>
        </div>

        <div style="padding: 2rem; background: #f9f9f9;">
            <h2 style="color: #1a1a2e;">Prenotazione confermata!</h2>
            <p>Ciao <strong>{nome_cliente}</strong>,</p>
            <p>La tua sessione di coaching VGC è confermata.</p>

            <div style="background: white; border-radius: 8px; padding: 1.5rem; margin: 1.5rem 0; border-left: 4px solid #e74c3c;">
                <h3 style="margin-top: 0; color: #555;">Dettagli sessione</h3>
                <p><strong>Data:</strong> {data_slot}</p>
                <p><strong>Orario:</strong> {ora_slot}</p>
                <p><strong>Durata:</strong> {durata} ora{"e" if durata > 1 else ""}</p>
                <p><strong>Totale:</strong> €{prezzo_euro:.2f}</p>
            </div>

            <div style="background: white; border-radius: 8px; padding: 1.5rem; margin: 1.5rem 0; border-left: 4px solid #1a1a2e;">
                <h3 style="margin-top: 0; color: #555;">Come contattarci</h3>
                <p>Per coordinare la sessione o per qualsiasi domanda, scrivimi su:</p>
                <p><strong>Discord:</strong> {COACH_DISCORD_TAG}</p>
                <p><strong>Telegram:</strong> {COACH_TELEGRAM_CONTACT}</p>
            </div>

            <p>Per qualsiasi altra domanda rispondi a questa email.</p>
        </div>

        <div style="background: #1a1a2e; padding: 1rem; text-align: center;">
            <p style="color: #888; font-size: 0.8rem; margin: 0;">VGC Coaching</p>
        </div>

    </div>
    """

    # Perché try/except invece di lasciare che un errore fermi tutto? Perché
    # l'invio di un'email dipende da un servizio ESTERNO (il server SMTP di
    # Gmail), che può avere un problema temporaneo, un timeout di rete, una
    # password per le app revocata... Se quell'errore facesse fallire
    # l'intera richiesta, un'email non consegnata bloccherebbe anche il
    # salvataggio della prenotazione nel database — anche se il vero
    # problema è solo "email non partita". Meglio "provare, e se fallisce
    # solo segnalarlo nei log (qui: stampandolo in console)", lasciando che
    # il resto dell'operazione vada comunque a buon fine. Ritrovi lo stesso
    # ragionamento in calendar_service.py e discord_service.py.
    try:
        _invia_via_gmail(email_cliente, "Prenotazione confermata", corpo_email)
        print(f"Email inviata a {email_cliente}")
    except Exception as e:
        print(f"Errore invio email DETTAGLIO: {type(e).__name__}: {e}")


def invia_promemoria_cliente(
    email_cliente: str,
    nome_cliente: str,
    data_slot: str,
    ora_slot: str,
    durata: int
):
    # Stessa identica struttura di invia_conferma_cliente qui sopra, solo
    # con testo diverso — mandata da backend/scheduler.py quando una
    # sessione si avvicina, invece che al momento della prenotazione.
    corpo_email = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">

        <div style="background: #1a1a2e; padding: 2rem; text-align: center;">
            <h1 style="color: white; margin: 0;">VGC Coaching</h1>
        </div>

        <div style="padding: 2rem; background: #f9f9f9;">
            <h2 style="color: #1a1a2e;">Promemoria sessione</h2>
            <p>Ciao <strong>{nome_cliente}</strong>,</p>
            <p>Ti ricordiamo che hai una sessione di coaching VGC in programma.</p>

            <div style="background: white; border-radius: 8px; padding: 1.5rem; margin: 1.5rem 0; border-left: 4px solid #e74c3c;">
                <h3 style="margin-top: 0; color: #555;">Dettagli sessione</h3>
                <p><strong>Data:</strong> {data_slot}</p>
                <p><strong>Orario:</strong> {ora_slot}</p>
                <p><strong>Durata:</strong> {durata} ora{"e" if durata > 1 else ""}</p>
            </div>

            <div style="background: white; border-radius: 8px; padding: 1.5rem; margin: 1.5rem 0; border-left: 4px solid #1a1a2e;">
                <h3 style="margin-top: 0; color: #555;">Come contattarci</h3>
                <p>Per coordinare la sessione o per qualsiasi domanda, scrivimi su:</p>
                <p><strong>Discord:</strong> {COACH_DISCORD_TAG}</p>
                <p><strong>Telegram:</strong> {COACH_TELEGRAM_CONTACT}</p>
            </div>

            <p>Ci vediamo presto!</p>
        </div>

        <div style="background: #1a1a2e; padding: 1rem; text-align: center;">
            <p style="color: #888; font-size: 0.8rem; margin: 0;">VGC Coaching</p>
        </div>

    </div>
    """

    try:
        _invia_via_gmail(email_cliente, "Promemoria: la tua sessione di coaching VGC si avvicina", corpo_email)
        print(f"Promemoria inviato a {email_cliente}")
    except Exception as e:
        print(f"Errore invio promemoria DETTAGLIO: {type(e).__name__}: {e}")


def invia_notifica_admin(
    nome_cliente: str,
    email_cliente: str,
    data_slot: str,
    ora_slot: str,
    durata: int,
    note_cliente: str
):
    # Questa email va al COACH (EMAIL_ADMIN), non allo studente — nota che
    # il destinatario passato a _invia_via_gmail più sotto è diverso
    # rispetto alle due funzioni precedenti (lì era email_cliente).
    corpo_email = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 2rem;">
        <h2 style="color: #e74c3c;">Nuova prenotazione ricevuta</h2>
        <div style="background: #f9f9f9; border-radius: 8px; padding: 1.5rem;">
            <p><strong>Cliente:</strong> {nome_cliente}</p>
            <p><strong>Email:</strong> {email_cliente}</p>
            <p><strong>Data:</strong> {data_slot}</p>
            <p><strong>Orario:</strong> {ora_slot}</p>
            <p><strong>Durata:</strong> {durata} ora{"e" if durata > 1 else ""}</p>
            <p><strong>Note:</strong> {note_cliente or "Nessuna nota"}</p>
        </div>
    </div>
    """
    # {note_cliente or "Nessuna nota"}: se note_cliente è una stringa vuota
    # o None, in Python questi valori sono "falsy" (contano come falso in
    # un contesto booleano), quindi "or" passa al secondo valore. È un modo
    # compatto per dire "usa note_cliente se c'è qualcosa di sensato,
    # altrimenti usa questo testo di default".

    try:
        _invia_via_gmail(EMAIL_ADMIN, f"Nuova prenotazione — {nome_cliente}", corpo_email)
        print("Notifica admin inviata")
    except Exception as e:
        print(f"Errore notifica admin DETTAGLIO: {type(e).__name__}: {e}")
