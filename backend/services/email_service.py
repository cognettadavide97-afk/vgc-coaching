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
import html
import base64
import logging
from email.message import EmailMessage
from dotenv import load_dotenv
from googleapiclient.discovery import build
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


# Ogni funzione di questo file costruisce il corpo dell'email con una
# f-string HTML, interpolando direttamente campi testo libero scritti dal
# cliente (nome, note, messaggio della consulenza...) — senza questa
# funzione, quel testo finirebbe nell'HTML COSÌ COM'È: un cliente che
# scrivesse `<a href="sito-di-phishing.com">Clicca qui</a>` come nota
# vedrebbe il coach ricevere un link vero e cliccabile nella sua casella
# (non JavaScript eseguibile — i client email lo filtrano — ma un vettore
# di phishing/tracking concreto). html.escape() trasforma i caratteri
# speciali dell'HTML (<, >, &, ...) nella loro forma "innocua" (&lt;,
# &gt;, &amp;...): il testo compare identico a come l'ha scritto il
# cliente, ma il client email lo mostra come TESTO, non lo interpreta più
# come markup. Va applicata qui, al momento di costruire l'HTML — non
# dove il dato viene raccolto, perché lo stesso testo libero (es.
# note_cliente) viene riusato altrove (pannello admin, webhook Discord)
# dove HTML-escaparlo sarebbe sbagliato o inutile.
def _escape(testo: str, default: str = "") -> str:
    return html.escape(testo) if testo else default


# Le due funzioni sotto factorizzano lo "scheletro" HTML (header/footer col
# logo, pannello grigio chiaro per il contenuto) che PRIMA veniva riscritto
# per intero in ogni singola funzione invia_*: 5 email al cliente
# condividevano lo stesso wrapper a tre blocchi (header + pannello + footer),
# 3 email al coach lo stesso wrapper più semplice (titolo + pannello). Ogni
# funzione invia_* qui sotto costruisce solo il proprio frammento di
# contenuto (corpo) e lo passa a una di queste due — un cambio di stile
# (es. il colore del footer) va fatto una volta sola invece che in 8 punti.
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


# Funzione condivisa da tutte le email qui sotto: costruisce il messaggio
# (con una versione testuale semplice + quella HTML vera e propria, così i
# client di posta che non mostrano HTML hanno comunque un contenuto
# leggibile), lo autentica scambiando il refresh_token con un token di
# accesso valido, e lo invia tramite l'API Gmail. Lo scambio NON avviene a
# ogni invio: credenziali_oauth_google (backend/services/google_oauth_service.py)
# tiene in cache le Credentials per refresh_token e chiama .refresh() solo
# quando l'access token non è più valido — vedi il commento in quel file per
# il perché (era un giro HTTPS a Google in più per ogni email). L'API vuole il
# messaggio codificato in base64 (formato "raw" richiesto da
# users.messages.send), non l'oggetto EmailMessage direttamente.
def _invia_via_gmail(destinatario: str, oggetto: str, corpo_html: str):
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
    """
    Controllo di salute, richiamato periodicamente dallo scheduler (vedi
    controlla_credenziali_gmail in backend/scheduler.py): prova a scambiare
    il refresh token per un token di accesso e a fare UNA chiamata Gmail
    che non manda nessuna email (users.getProfile — restituisce solo dati
    sull'account, tipo diagnostico "sono ancora autorizzato?"). Restituisce
    True se tutto ok, False altrimenti — non solleva mai un'eccezione verso
    il chiamante, così un fallimento qui non può mai far crashare lo
    scheduler.

    Perché serve: con l'app Google OAuth ancora in stato "Testing" (vedi
    README.md, sezione Gmail API), il refresh token scade dopo 7 giorni —
    a prescindere dall'uso che se ne fa, non dopo 7 giorni di INATTIVITÀ come
    si era creduto a lungo. Osservato in produzione il 2026-09-02: il token è
    scaduto pur essendo esercitato ogni giorno proprio da questo controllo e
    dalle email di ogni prenotazione. Questo healthcheck quindi RILEVA la
    scadenza, non la previene: l'unico rimedio che la elimina è portare la
    schermata di consenso a "In production". È comunque un problema
    silenzioso, perché finché nessuno controlla esplicitamente lo si
    scoprirebbe solo quando un'email a un cliente non parte. Questo controllo
    lo scopre PRIMA, e avvisa il coach via Discord
    (vedi invia_alert_sistema in backend/services/discord_service.py) così
    può rifare l'autorizzazione con scripts/reauth_gmail.py.
    """
    try:
        credenziali = credenziali_oauth_google(GMAIL_REFRESH_TOKEN, GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET)
        servizio = build("gmail", "v1", credentials=credenziali)
        servizio.users().getProfile(userId="me").execute()
        return True
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

    # {"e" if durata > 1 else ""} è un'espressione condizionale (l'"if" in
    # una riga sola, equivalente a scrivere "e" if durata > 1 else "")
    # dentro la f-string: serve solo per scrivere "1 ora" ma "2 ore" — una
    # piccola concordanza grammaticale automatica.
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
    # Stesso contenuto/struttura di invia_conferma_cliente qui sopra, solo
    # con testo diverso — mandata da backend/scheduler.py quando una
    # sessione si avvicina, invece che al momento della prenotazione.
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
