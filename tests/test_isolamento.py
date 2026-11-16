# Prova che la suite non può raggiungere i servizi veri (voce 51), anche sul
# PC di sviluppo, dove il .env contiene le credenziali reali. Le due reti
# stanno in tests/conftest.py; qui si verifica che reggano.

import socket

import pytest

import backend.database as database
import backend.routers.discord_auth as discord_auth
import backend.services.backup_service as backup_service
import backend.services.calendar_service as calendar_service
import backend.services.discord_service as discord_service
import backend.services.email_service as email_service


def test_le_credenziali_delle_integrazioni_sono_vuote():
    """Prima rete: i servizi leggono le credenziali all'import, e devono averle trovate vuote."""
    credenziali = {
        "GMAIL_CLIENT_ID": email_service.GMAIL_CLIENT_ID,
        "GMAIL_CLIENT_SECRET": email_service.GMAIL_CLIENT_SECRET,
        "GMAIL_REFRESH_TOKEN": email_service.GMAIL_REFRESH_TOKEN,
        "DRIVE_REFRESH_TOKEN": backup_service.DRIVE_REFRESH_TOKEN,
        "GOOGLE_DRIVE_BACKUP_FOLDER_ID": backup_service.DRIVE_FOLDER_ID,
        "GOOGLE_SERVICE_ACCOUNT_EMAIL": calendar_service.SERVICE_ACCOUNT_EMAIL,
        "GOOGLE_PRIVATE_KEY": calendar_service.PRIVATE_KEY,
        "GOOGLE_CALENDAR_ID": calendar_service.CALENDAR_ID,
        "DISCORD_WEBHOOK_URL": discord_service.DISCORD_WEBHOOK_URL,
        "DISCORD_CLIENT_ID": discord_auth.DISCORD_CLIENT_ID,
        "DISCORD_CLIENT_SECRET": discord_auth.DISCORD_CLIENT_SECRET,
    }
    piene = [nome for nome, valore in credenziali.items() if valore]
    assert piene == [], f"credenziali lette dal .env vero: {piene}"


def test_il_database_dei_servizi_e_sqlite_in_memoria():
    """SessionLocal ed engine, usati da scheduler e backup, non puntano al MySQL di sviluppo."""
    assert str(database.engine.url) == "sqlite:///:memory:"


def test_una_connessione_verso_l_esterno_viene_bloccata():
    """
    Seconda rete. 203.0.113.1 è un indirizzo riservato alla documentazione
    (RFC 5737), che nessuno instrada: anche senza il blocco il test non
    raggiungerebbe nessun servizio, fallirebbe solo per timeout.
    """
    with pytest.raises(RuntimeError, match="verso l'esterno"):
        socket.create_connection(("203.0.113.1", 443), timeout=1)


def test_le_connessioni_locali_restano_permesse():
    """Il loopback serve al motore asincrono di TestClient su Windows: bloccarlo romperebbe la suite."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    try:
        client = socket.create_connection(server.getsockname(), timeout=1)
        client.close()
    finally:
        server.close()
