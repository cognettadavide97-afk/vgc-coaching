"""Composizione e invio delle email transazionali, tramite API Gmail.

L'invio passa dall'API HTTPS e non da SMTP perché l'hosting blocca le
connessioni SMTP in uscita (`Network is unreachable`). Il costo di questa
scelta è l'autenticazione OAuth2: serve un refresh token ottenuto una
tantum autorizzando l'app dal browser, non una password.

Nessuna funzione di invio propaga eccezioni: un problema con Gmail non
deve far fallire l'operazione che ha generato l'email.
"""

import os
import html
import base64
import logging
from email.message import EmailMessage
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from backend.services.google_oauth_service import credenziali_oauth_google

load_dotenv()

GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")
GMAIL_REFRESH_TOKEN = os.getenv("GMAIL_REFRESH_TOKEN")
EMAIL_MITTENTE = os.getenv("EMAIL_MITTENTE")
EMAIL_ADMIN = os.getenv("EMAIL_ADMIN")
COACH_DISCORD_TAG = os.getenv("COACH_DISCORD_TAG")
COACH_TELEGRAM_CONTACT = os.getenv("COACH_TELEGRAM_CONTACT")

logger = logging.getLogger(__name__)


def _escape(testo: str, default: str = "") -> str:
    """Neutralizza il markup nel testo scritto dal cliente.

    I corpi delle email sono costruiti per interpolazione, quindi un campo
    libero non filtrato diventerebbe HTML attivo: una nota contenente un
    tag `<a>` arriverebbe al coach come link cliccabile.

    L'escape va applicato qui e non alla raccolta del dato: lo stesso testo
    viene riusato nel pannello e nelle notifiche Discord, dove servono
    trattamenti diversi.
    """
    return html.escape(testo) if testo else default


# Scheletro HTML condiviso: le funzioni di invio producono solo il proprio
# frammento di contenuto, così una modifica di stile si fa in un punto solo.
def _template_cliente(corpo: str) -> str:
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">

        <div style="background: #1a1a2e; padding: 2rem; text-align: center;">
            <h1 style="color: white; margin: 0;">VGC Coaching</h1>
        </div>

        <div style="padding: 2rem; background: #f9f9f9;">
            {corpo}
        </div>

        <div style="background: #1a1a2e; padding: 1rem; text-align: center;">
            <p style="color: #888; font-size: 0.8rem; margin: 0;">VGC Coaching</p>
        </div>

    </div>
    """


def _template_admin(titolo: str, corpo: str) -> str:
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 2rem;">
        <h2 style="color: #e74c3c;">{titolo}</h2>
        <div style="background: #f9f9f9; border-radius: 8px; padding: 1.5rem;">
            {corpo}
        </div>
    </div>
    """


def _invia_via_gmail(destinatario: str, oggetto: str, corpo_html: str):
    """Invia un messaggio multipart via API Gmail. Punto unico di invio.

    Include una versione testuale oltre a quella HTML, per i client che non
    interpretano il markup. L'API richiede il messaggio codificato in
    base64 url-safe.
    """
    messaggio = EmailMessage()
    messaggio["From"] = EMAIL_MITTENTE
    messaggio["To"] = destinatario
    messaggio["Subject"] = oggetto
    messaggio.set_content("Questa email richiede un client che supporta l'HTML per essere visualizzata correttamente.")
    messaggio.add_alternative(corpo_html, subtype="html")

    credenziali = credenziali_oauth_google(GMAIL_REFRESH_TOKEN, GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET)
    servizio = build("gmail", "v1", credentials=credenziali)
    raw = base64.urlsafe_b64encode(messaggio.as_bytes()).decode()
    servizio.users().messages().send(userId="me", body={"raw": raw}).execute()


def verifica_credenziali_gmail() -> bool:
    """Verifica che il refresh token Gmail sia ancora spendibile.

    La sonda è lo **scambio del refresh token con un access token**, cioè
    esattamente l'operazione che fallisce quando il token scade o viene
    revocato: il guasto che questo controllo esiste per intercettare.

    Non interroga l'API Gmail, e non è un dettaglio: lo scope concesso è
    `gmail.send`, che autorizza a spedire e a nient'altro. Una lettura di
    prova — `users.getProfile()`, che questa funzione usava fino al
    2026-09-04 — risponde 403 "insufficient authentication scopes" anche
    con credenziali perfettamente sane, quindi come sonda mentiva:
    dichiarava fermo un invio email che funzionava. Il refresh forzato non
    ha quel problema, perché non dipende da nessuno scope.

    Il `refresh()` esplicito serve a non fidarsi della cache di
    `credenziali_oauth_google`: un access token ancora fresco proverebbe
    solo che il controllo precedente era andato bene.

    Restituisce l'esito invece di sollevare, così un fallimento non
    interrompe lo scheduler che la richiama.
    """
    try:
        credenziali = credenziali_oauth_google(GMAIL_REFRESH_TOKEN, GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET)
        credenziali.refresh(Request())
        return credenziali.token is not None
    except Exception:
        logger.exception("Controllo credenziali Gmail fallito")
        return False


def invia_conferma_cliente(
    email_cliente: str,
    nome_cliente: str,
    data_slot: str,
    ora_slot: str,
    durata: int,
    prezzo: int
):
    prezzo_euro = prezzo / 100

    corpo = f"""
            <h2 style="color: #1a1a2e;">Booking confirmed!</h2>
            <p>Hi <strong>{_escape(nome_cliente)}</strong>,</p>
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
    """
    corpo_email = _template_cliente(corpo)

    try:
        _invia_via_gmail(email_cliente, "Booking confirmed", corpo_email)
        logger.info(f"Email inviata a {email_cliente}")
    except Exception:
        logger.exception("Errore invio email")


def invia_promemoria_cliente(
    email_cliente: str,
    nome_cliente: str,
    data_slot: str,
    ora_slot: str,
    durata: int
):
    # Inviata dallo scheduler quando la sessione si avvicina.
    corpo = f"""
            <h2 style="color: #1a1a2e;">Session reminder</h2>
            <p>Hi <strong>{_escape(nome_cliente)}</strong>,</p>
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
    """
    corpo_email = _template_cliente(corpo)

    try:
        _invia_via_gmail(email_cliente, "Reminder: your VGC coaching session is coming up", corpo_email)
        logger.info(f"Promemoria inviato a {email_cliente}")
    except Exception:
        logger.exception("Errore invio promemoria")


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
    #
    # _escape(...) chiamata inline qui sotto, non riassegnata a inizio
    # funzione (come in invia_conferma_cliente): l'oggetto dell'email due
    # righe più sotto ("Nuova prenotazione — {nome_cliente}") vuole il nome
    # ORIGINALE — l'oggetto non è HTML, escaparlo lì mostrerebbe
    # letteralmente "&amp;" invece di "&" nella casella del coach.
    corpo = f"""
            <p><strong>Cliente:</strong> {_escape(nome_cliente)}</p>
            <p><strong>Email:</strong> {_escape(email_cliente)}</p>
            <p><strong>Data:</strong> {data_slot}</p>
            <p><strong>Orario:</strong> {ora_slot}</p>
            <p><strong>Durata:</strong> {durata} ora{"e" if durata > 1 else ""}</p>
            <p><strong>Note:</strong> {_escape(note_cliente, "Nessuna nota")}</p>
    """
    corpo_email = _template_admin("Nuova prenotazione ricevuta", corpo)

    try:
        _invia_via_gmail(EMAIL_ADMIN, f"Nuova prenotazione — {nome_cliente}", corpo_email)
        logger.info("Notifica admin inviata")
    except Exception:
        logger.exception("Errore notifica admin")


def invia_conferma_richiesta_consulenza(email_cliente: str, nome_cliente: str):
    """
    Conferma al cliente che la sua richiesta di call gratuita (20 minuti) è
    arrivata — vedi backend/routers/consulenza.py. A differenza di
    invia_conferma_cliente, qui NON c'è un orario da confermare: la call
    va accordata privatamente, quindi il messaggio resta volutamente vago
    su data/ora.
    """
    corpo = f"""
            <h2 style="color: #1a1a2e;">Request received!</h2>
            <p>Hi <strong>{_escape(nome_cliente)}</strong>,</p>
            <p>We've received your request for a free 20-minute call. We'll get in touch shortly to arrange a time.</p>
    """
    corpo_email = _template_cliente(corpo)

    try:
        _invia_via_gmail(email_cliente, "Free call request received", corpo_email)
        logger.info(f"Conferma richiesta consulenza inviata a {email_cliente}")
    except Exception:
        logger.exception("Errore invio conferma richiesta consulenza")


def invia_notifica_richiesta_consulenza_admin(
    nome_cliente: str,
    email_cliente: str,
    discord_tag: str,
    messaggio: str
):
    """Avvisa il coach (EMAIL_ADMIN) di una nuova richiesta di call gratuita."""
    corpo = f"""
            <p><strong>Cliente:</strong> {_escape(nome_cliente)}</p>
            <p><strong>Email:</strong> {_escape(email_cliente)}</p>
            <p><strong>Discord:</strong> {_escape(discord_tag, "non specificato")}</p>
            <p><strong>Messaggio:</strong> {_escape(messaggio, "nessuno")}</p>
    """
    corpo_email = _template_admin("Nuova richiesta di call gratuita (20 min)", corpo)

    try:
        _invia_via_gmail(EMAIL_ADMIN, f"Richiesta call gratuita — {nome_cliente}", corpo_email)
        logger.info("Notifica admin richiesta consulenza inviata")
    except Exception:
        logger.exception("Errore notifica admin richiesta consulenza")


def invia_conferma_richiesta_pacchetto(email_cliente: str, nome_cliente: str, nome_pacchetto: str):
    """
    Conferma al cliente che la sua richiesta di attivazione pacchetto è
    arrivata — vedi backend/routers/pacchetti_richieste.py. Come per la
    consulenza gratuita, nessun pagamento avviene qui: il coach ricontatta
    per accordare il pagamento e solo dopo assegna il pacchetto vero da
    /admin/pacchetti.
    """
    corpo = f"""
            <h2 style="color: #1a1a2e;">Request received!</h2>
            <p>Hi <strong>{_escape(nome_cliente)}</strong>,</p>
            <p>We've received your request to activate the <strong>{nome_pacchetto}</strong> package. We'll get in touch shortly to arrange payment and get it set up.</p>
    """
    corpo_email = _template_cliente(corpo)

    try:
        _invia_via_gmail(email_cliente, "Package request received", corpo_email)
        logger.info(f"Conferma richiesta pacchetto inviata a {email_cliente}")
    except Exception:
        logger.exception("Errore invio conferma richiesta pacchetto")


def invia_notifica_richiesta_pacchetto_admin(
    nome_cliente: str,
    email_cliente: str,
    discord_tag: str,
    nome_pacchetto: str,
    messaggio: str
):
    """Avvisa il coach (EMAIL_ADMIN) di una nuova richiesta di attivazione pacchetto."""
    corpo = f"""
            <p><strong>Cliente:</strong> {_escape(nome_cliente)}</p>
            <p><strong>Email:</strong> {_escape(email_cliente)}</p>
            <p><strong>Discord:</strong> {_escape(discord_tag, "non specificato")}</p>
            <p><strong>Messaggio:</strong> {_escape(messaggio, "nessuno")}</p>
    """
    corpo_email = _template_admin(f"Nuova richiesta pacchetto — {nome_pacchetto}", corpo)

    try:
        _invia_via_gmail(EMAIL_ADMIN, f"Richiesta pacchetto {nome_pacchetto} — {nome_cliente}", corpo_email)
        logger.info("Notifica admin richiesta pacchetto inviata")
    except Exception:
        logger.exception("Errore notifica admin richiesta pacchetto")


def invia_richiesta_recensione(email_cliente: str, nome_cliente: str, link_recensione: str):
    """
    Mandata una volta sola dopo che la sessione è passata (vedi il job
    controlla_e_invia_richieste_recensione in backend/scheduler.py), con un
    link univoco che porta alla pagina pubblica frontend/recensione.html.
    """
    corpo = f"""
            <h2 style="color: #1a1a2e;">How did it go?</h2>
            <p>Hi <strong>{_escape(nome_cliente)}</strong>,</p>
            <p>I hope the session was useful! If you have a minute, leave me a rating and a comment — it really helps me improve.</p>

            <div style="text-align: center; margin: 1.5rem 0;">
                <a href="{link_recensione}" style="display: inline-block; padding: 0.9rem 1.5rem; background: #e74c3c; color: white; text-decoration: none; border-radius: 8px; font-weight: 600;">
                    Leave a review
                </a>
            </div>
    """
    corpo_email = _template_cliente(corpo)

    try:
        _invia_via_gmail(email_cliente, "How did your session go?", corpo_email)
        logger.info(f"Richiesta recensione inviata a {email_cliente}")
    except Exception:
        logger.exception("Errore invio richiesta recensione")
