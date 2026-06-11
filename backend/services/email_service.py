import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from dotenv import load_dotenv

# prova a caricare il .env con il percorso assoluto
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
EMAIL_MITTENTE = os.getenv("EMAIL_MITTENTE")
EMAIL_ADMIN = os.getenv("EMAIL_ADMIN")

def invia_conferma_cliente(
    email_cliente: str,
    nome_cliente: str,
    data_slot: str,
    ora_slot: str,
    durata: int,
    prezzo: int
):
    prezzo_euro = prezzo / 100

    corpo_email = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #1a1a2e; padding: 2rem; text-align: center;">
            <h1 style="color: white; margin: 0;">VGC Coaching</h1>
        </div>
        <div style="padding: 2rem; background: #f9f9f9;">
            <h2 style="color: #1a1a2e;">Prenotazione confermata!</h2>
            <p>Ciao <strong>{nome_cliente}</strong>,</p>
            <p>La tua sessione di coaching VGC è stata prenotata con successo.</p>
            <div style="background: white; border-radius: 8px; padding: 1.5rem; margin: 1.5rem 0; border-left: 4px solid #e74c3c;">
                <h3 style="margin-top: 0; color: #555;">Dettagli sessione</h3>
                <p><strong>Data:</strong> {data_slot}</p>
                <p><strong>Orario:</strong> {ora_slot}</p>
                <p><strong>Durata:</strong> {durata} ora{"e" if durata > 1 else ""}</p>
                <p><strong>Totale:</strong> €{prezzo_euro:.2f}</p>
            </div>
            <p>Ci vediamo presto su Pokémon Showdown!</p>
        </div>
        <div style="background: #1a1a2e; padding: 1rem; text-align: center;">
            <p style="color: #888; font-size: 0.8rem; margin: 0;">VGC Coaching</p>
        </div>
    </div>
    """

    messaggio = Mail(
        from_email=EMAIL_MITTENTE,
        to_emails=email_cliente,
        subject="Prenotazione confermata — VGC Coaching",
        html_content=corpo_email
    )

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(messaggio)
        print(f"Email inviata a {email_cliente} — status: {response.status_code}")
    except Exception as e:
        print(f"Errore invio email DETTAGLIO: {type(e).__name__}: {e}")


def invia_notifica_admin(
    nome_cliente: str,
    email_cliente: str,
    data_slot: str,
    ora_slot: str,
    durata: int,
    note_cliente: str
):
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

    messaggio = Mail(
        from_email=EMAIL_MITTENTE,
        to_emails=EMAIL_ADMIN,
        subject=f"Nuova prenotazione — {nome_cliente}",
        html_content=corpo_email
    )

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(messaggio)
        print(f"Notifica admin inviata — status: {response.status_code}")
    except Exception as e:
        print(f"Errore notifica admin DETTAGLIO: {type(e).__name__}: {e}")