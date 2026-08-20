# Questo file si occupa di UNA cosa sola: costruire e inviare le email
# dell'app (conferma prenotazione, promemoria, notifica al coach), usando
# l'API Gmail di Google come "postino" — un programma normale non può
# "inviare email" da solo: ha bisogno di appoggiarsi al server di
# qualcuno, in questo caso lo stesso account Gmail del coach.
#
# Perché l'API via HTTPS e non SMTP diretto (che sarebbe più semplice)?
# Perché Railway (come molte piattaforme cloud) blocca le connessioni SMTP
# in uscita per evitare che i suoi server vengano usati per spam — un
# tentativo reale di invio SMTP da lì fallisce con "Network is
# unreachable". L'API Gmail invece è una normale chiamata HTTPS (stessa
# porta 443 di qualunque sito web), mai bloccata. Il prezzo da pagare è
# l'autenticazione: non basta una password, serve OAuth2 — un
# "refresh token" ottenuto una tantum autorizzando l'app dal browser (vedi
# lo script usato in fase di setup), che l'API di Google scambia ad ogni
# invio con un token di accesso temporaneo tramite Credentials.refresh().
# google-auth e google-api-python-client sono già dipendenze del progetto
# (usate anche da calendar_service.py per lo stesso tipo di autenticazione).
#
# Pattern che vedrai ripetuto in ogni funzione di questo file: costruire il
# contenuto, provare a inviarlo, e se qualcosa va storto stampare l'errore
# invece di far fallire tutta la richiesta. Guarda il commento dentro
# invia_conferma_cliente per il perché di questa scelta.

import os
import base64
from email.message import EmailMessage
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

load_dotenv()

GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")
GMAIL_REFRESH_TOKEN = os.getenv("GMAIL_REFRESH_TOKEN")
EMAIL_MITTENTE = os.getenv("EMAIL_MITTENTE")
EMAIL_ADMIN = os.getenv("EMAIL_ADMIN")
COACH_DISCORD_TAG = os.getenv("COACH_DISCORD_TAG")
COACH_TELEGRAM_CONTACT = os.getenv("COACH_TELEGRAM_CONTACT")


# Funzione condivisa dalle tre email qui sotto: costruisce il messaggio
# (con una versione testuale semplice + quella HTML vera e propria, così i
# client di posta che non mostrano HTML hanno comunque un contenuto
# leggibile), lo autentica scambiando il refresh_token con un token di
# accesso valido (Credentials.refresh() fa una chiamata HTTPS a Google per
# ottenerlo — dura poco, per questo va rifatta ad ogni invio invece di
# essere salvata), e lo invia tramite l'API Gmail. L'API vuole il
# messaggio codificato in base64 (formato "raw" richiesto da
# users.messages.send), non l'oggetto EmailMessage direttamente.
def _invia_via_gmail(destinatario: str, oggetto: str, corpo_html: str):
    messaggio = EmailMessage()
    messaggio["From"] = EMAIL_MITTENTE
    messaggio["To"] = destinatario
    messaggio["Subject"] = oggetto
    messaggio.set_content("Questa email richiede un client che supporta l'HTML per essere visualizzata correttamente.")
    messaggio.add_alternative(corpo_html, subtype="html")

    credenziali = Credentials(
        token=None,
        refresh_token=GMAIL_REFRESH_TOKEN,
        client_id=GMAIL_CLIENT_ID,
        client_secret=GMAIL_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
    )
    credenziali.refresh(Request())

    servizio = build("gmail", "v1", credentials=credenziali)
    raw = base64.urlsafe_b64encode(messaggio.as_bytes()).decode()
    servizio.users().messages().send(userId="me", body={"raw": raw}).execute()


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
            <h2 style="color: #1a1a2e;">Booking confirmed!</h2>
            <p>Hi <strong>{nome_cliente}</strong>,</p>
            <p>Your VGC coaching session is confirmed.</p>

            <div style="background: white; border-radius: 8px; padding: 1.5rem; margin: 1.5rem 0; border-left: 4px solid #e74c3c;">
                <h3 style="margin-top: 0; color: #555;">Session details</h3>
                <p><strong>Date:</strong> {data_slot}</p>
                <p><strong>Time:</strong> {ora_slot}</p>
                <p><strong>Duration:</strong> {durata} hour{"s" if durata > 1 else ""}</p>
                <p><strong>Total:</strong> €{prezzo_euro:.2f}</p>
            </div>

            <div style="background: white; border-radius: 8px; padding: 1.5rem; margin: 1.5rem 0; border-left: 4px solid #1a1a2e;">
                <h3 style="margin-top: 0; color: #555;">How to reach us</h3>
                <p>To coordinate the session or for any question, message me on:</p>
                <p><strong>Discord:</strong> {COACH_DISCORD_TAG}</p>
                <p><strong>Telegram:</strong> {COACH_TELEGRAM_CONTACT}</p>
            </div>

            <p>For any other question, just reply to this email.</p>
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
        _invia_via_gmail(email_cliente, "Booking confirmed", corpo_email)
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
            <h2 style="color: #1a1a2e;">Session reminder</h2>
            <p>Hi <strong>{nome_cliente}</strong>,</p>
            <p>Just a reminder that you have a VGC coaching session coming up.</p>

            <div style="background: white; border-radius: 8px; padding: 1.5rem; margin: 1.5rem 0; border-left: 4px solid #e74c3c;">
                <h3 style="margin-top: 0; color: #555;">Session details</h3>
                <p><strong>Date:</strong> {data_slot}</p>
                <p><strong>Time:</strong> {ora_slot}</p>
                <p><strong>Duration:</strong> {durata} hour{"s" if durata > 1 else ""}</p>
            </div>

            <div style="background: white; border-radius: 8px; padding: 1.5rem; margin: 1.5rem 0; border-left: 4px solid #1a1a2e;">
                <h3 style="margin-top: 0; color: #555;">How to reach us</h3>
                <p>To coordinate the session or for any question, message me on:</p>
                <p><strong>Discord:</strong> {COACH_DISCORD_TAG}</p>
                <p><strong>Telegram:</strong> {COACH_TELEGRAM_CONTACT}</p>
            </div>

            <p>See you soon!</p>
        </div>

        <div style="background: #1a1a2e; padding: 1rem; text-align: center;">
            <p style="color: #888; font-size: 0.8rem; margin: 0;">VGC Coaching</p>
        </div>

    </div>
    """

    try:
        _invia_via_gmail(email_cliente, "Reminder: your VGC coaching session is coming up", corpo_email)
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


def invia_conferma_richiesta_consulenza(email_cliente: str, nome_cliente: str):
    """
    Conferma al cliente che la sua richiesta di call gratuita (20 minuti) è
    arrivata — vedi backend/routers/consulenza.py. A differenza di
    invia_conferma_cliente, qui NON c'è un orario da confermare: la call
    va accordata privatamente, quindi il messaggio resta volutamente vago
    su data/ora.
    """
    corpo_email = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">

        <div style="background: #1a1a2e; padding: 2rem; text-align: center;">
            <h1 style="color: white; margin: 0;">VGC Coaching</h1>
        </div>

        <div style="padding: 2rem; background: #f9f9f9;">
            <h2 style="color: #1a1a2e;">Request received!</h2>
            <p>Hi <strong>{nome_cliente}</strong>,</p>
            <p>We've received your request for a free 20-minute call. We'll get in touch shortly to arrange a time.</p>
        </div>

        <div style="background: #1a1a2e; padding: 1rem; text-align: center;">
            <p style="color: #888; font-size: 0.8rem; margin: 0;">VGC Coaching</p>
        </div>

    </div>
    """

    try:
        _invia_via_gmail(email_cliente, "Free call request received", corpo_email)
        print(f"Conferma richiesta consulenza inviata a {email_cliente}")
    except Exception as e:
        print(f"Errore invio conferma richiesta consulenza DETTAGLIO: {type(e).__name__}: {e}")


def invia_notifica_richiesta_consulenza_admin(
    nome_cliente: str,
    email_cliente: str,
    discord_tag: str,
    messaggio: str
):
    """Avvisa il coach (EMAIL_ADMIN) di una nuova richiesta di call gratuita."""
    corpo_email = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 2rem;">
        <h2 style="color: #e74c3c;">Nuova richiesta di call gratuita (20 min)</h2>
        <div style="background: #f9f9f9; border-radius: 8px; padding: 1.5rem;">
            <p><strong>Cliente:</strong> {nome_cliente}</p>
            <p><strong>Email:</strong> {email_cliente}</p>
            <p><strong>Discord:</strong> {discord_tag or "non specificato"}</p>
            <p><strong>Messaggio:</strong> {messaggio or "nessuno"}</p>
        </div>
    </div>
    """

    try:
        _invia_via_gmail(EMAIL_ADMIN, f"Richiesta call gratuita — {nome_cliente}", corpo_email)
        print("Notifica admin richiesta consulenza inviata")
    except Exception as e:
        print(f"Errore notifica admin richiesta consulenza DETTAGLIO: {type(e).__name__}: {e}")


def invia_conferma_richiesta_pacchetto(email_cliente: str, nome_cliente: str, nome_pacchetto: str):
    """
    Conferma al cliente che la sua richiesta di attivazione pacchetto è
    arrivata — vedi backend/routers/pacchetti_richieste.py. Come per la
    consulenza gratuita, nessun pagamento avviene qui: il coach ricontatta
    per accordare il pagamento e solo dopo assegna il pacchetto vero da
    /admin/pacchetti.
    """
    corpo_email = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">

        <div style="background: #1a1a2e; padding: 2rem; text-align: center;">
            <h1 style="color: white; margin: 0;">VGC Coaching</h1>
        </div>

        <div style="padding: 2rem; background: #f9f9f9;">
            <h2 style="color: #1a1a2e;">Request received!</h2>
            <p>Hi <strong>{nome_cliente}</strong>,</p>
            <p>We've received your request to activate the <strong>{nome_pacchetto}</strong> package. We'll get in touch shortly to arrange payment and get it set up.</p>
        </div>

        <div style="background: #1a1a2e; padding: 1rem; text-align: center;">
            <p style="color: #888; font-size: 0.8rem; margin: 0;">VGC Coaching</p>
        </div>

    </div>
    """

    try:
        _invia_via_gmail(email_cliente, "Package request received", corpo_email)
        print(f"Conferma richiesta pacchetto inviata a {email_cliente}")
    except Exception as e:
        print(f"Errore invio conferma richiesta pacchetto DETTAGLIO: {type(e).__name__}: {e}")


def invia_notifica_richiesta_pacchetto_admin(
    nome_cliente: str,
    email_cliente: str,
    discord_tag: str,
    nome_pacchetto: str,
    messaggio: str
):
    """Avvisa il coach (EMAIL_ADMIN) di una nuova richiesta di attivazione pacchetto."""
    corpo_email = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 2rem;">
        <h2 style="color: #e74c3c;">Nuova richiesta pacchetto — {nome_pacchetto}</h2>
        <div style="background: #f9f9f9; border-radius: 8px; padding: 1.5rem;">
            <p><strong>Cliente:</strong> {nome_cliente}</p>
            <p><strong>Email:</strong> {email_cliente}</p>
            <p><strong>Discord:</strong> {discord_tag or "non specificato"}</p>
            <p><strong>Messaggio:</strong> {messaggio or "nessuno"}</p>
        </div>
    </div>
    """

    try:
        _invia_via_gmail(EMAIL_ADMIN, f"Richiesta pacchetto {nome_pacchetto} — {nome_cliente}", corpo_email)
        print("Notifica admin richiesta pacchetto inviata")
    except Exception as e:
        print(f"Errore notifica admin richiesta pacchetto DETTAGLIO: {type(e).__name__}: {e}")


def invia_richiesta_recensione(email_cliente: str, nome_cliente: str, link_recensione: str):
    """
    Mandata una volta sola dopo che la sessione è passata (vedi il job
    controlla_e_invia_richieste_recensione in backend/scheduler.py), con un
    link univoco che porta alla pagina pubblica frontend/recensione.html.
    """
    corpo_email = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">

        <div style="background: #1a1a2e; padding: 2rem; text-align: center;">
            <h1 style="color: white; margin: 0;">VGC Coaching</h1>
        </div>

        <div style="padding: 2rem; background: #f9f9f9;">
            <h2 style="color: #1a1a2e;">How did it go?</h2>
            <p>Hi <strong>{nome_cliente}</strong>,</p>
            <p>I hope the session was useful! If you have a minute, leave me a rating and a comment — it really helps me improve.</p>

            <div style="text-align: center; margin: 1.5rem 0;">
                <a href="{link_recensione}" style="display: inline-block; padding: 0.9rem 1.5rem; background: #e74c3c; color: white; text-decoration: none; border-radius: 8px; font-weight: 600;">
                    Leave a review
                </a>
            </div>
        </div>

        <div style="background: #1a1a2e; padding: 1rem; text-align: center;">
            <p style="color: #888; font-size: 0.8rem; margin: 0;">VGC Coaching</p>
        </div>

    </div>
    """

    try:
        _invia_via_gmail(email_cliente, "How did your session go?", corpo_email)
        print(f"Richiesta recensione inviata a {email_cliente}")
    except Exception as e:
        print(f"Errore invio richiesta recensione DETTAGLIO: {type(e).__name__}: {e}")
