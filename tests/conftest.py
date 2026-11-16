# Configurazione condivisa da tutti i test (pytest la carica automaticamente,
# non va importata a mano). Due decisioni chiave, spiegate qui invece che
# ripetute in ogni file di test:
#
# 1. Database di test: SQLite in memoria, non il MySQL di sviluppo. I test
#    devono poter girare ovunque (anche in CI, senza un server MySQL
#    disponibile) e partire sempre da uno stato pulito — un database che
#    vive solo nella RAM e sparisce a fine test soddisfa entrambe le cose.
#    ":memory:" da solo creerebbe un database diverso per ogni connessione;
#    StaticPool costringe SQLAlchemy a riusare sempre la STESSA connessione,
#    così tutte le richieste della sessione di test vedono lo stesso database.
#
# 2. Integrazioni esterne irraggiungibili: i test non devono MAI mandare email
#    vere, messaggi Discord veri o creare eventi sul calendario Google vero,
#    e sul PC di sviluppo il .env contiene le credenziali reali. Due reti,
#    indipendenti (voce 51):
#    - le credenziali si svuotano qui sotto, PRIMA di importare il backend;
#    - la fixture `rete_esterna_bloccata` fa fallire ogni connessione che
#      esce dalla macchina, e ferma anche ciò che la prima rete non conosce
#      (una variabile dimenticata, un servizio aggiunto domani).
#    Le funzioni sostituite in `integrazioni_esterne_finte` non sono più la
#    protezione: tengono i test veloci e i log puliti.

import os
import socket

# Prima rete. I servizi leggono le credenziali una volta sola, all'import
# del proprio modulo: svuotarle dopo gli import qui sotto non le
# raggiungerebbe più. load_dotenv() non sovrascrive una variabile già
# presente nell'ambiente, anche se vuota, quindi il .env vero viene
# ignorato per queste chiavi. DATABASE_URL come nella CI: SessionLocal ed
# engine, usati direttamente da scheduler e backup, non devono poter
# scrivere sul MySQL di sviluppo se un test dimentica di sostituirli.
CREDENZIALI_INTEGRAZIONI = (
    "GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN",
    "DRIVE_REFRESH_TOKEN", "GOOGLE_DRIVE_BACKUP_FOLDER_ID",
    "GOOGLE_SERVICE_ACCOUNT_EMAIL", "GOOGLE_PRIVATE_KEY", "GOOGLE_CALENDAR_ID",
    "DISCORD_WEBHOOK_URL", "DISCORD_CLIENT_ID", "DISCORD_CLIENT_SECRET",
)
for _nome in CREDENZIALI_INTEGRAZIONI:
    os.environ[_nome] = ""
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.database import Base, get_db
import backend.models  # registra tutti i model su Base.metadata (vedi backend/models/__init__.py)
from backend.main import app
from backend.rate_limit import limiter
from backend.models.slots import Slot
from backend.services.auth_service import crea_token, crea_token_studente

TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

@event.listens_for(TEST_ENGINE, "connect")
def _attiva_chiavi_esterne(connessione_dbapi, _record):
    """
    SQLite legge le FOREIGN KEY dichiarate nei model, le registra... e poi
    NON le applica: per compatibilità con le versioni storiche il controllo
    è disattivato di default e va acceso con un PRAGMA, per ogni connessione.
    MySQL (sviluppo locale e produzione) le applica sempre e non si possono
    spegnere: senza questa riga il database della suite è più permissivo di
    quello vero, e i test certificano come funzionanti operazioni che in
    produzione finiscono con un errore 1451 e un 500.

    Va fatto sull'evento "connect" perché il PRAGMA viene ignorato in
    silenzio se eseguito dentro una transazione già aperta. Con StaticPool
    la connessione è una sola e riusata, quindi scatta una volta per sessione
    di test.
    """
    cursore = connessione_dbapi.cursor()
    cursore.execute("PRAGMA foreign_keys=ON")
    cursore.close()


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db

# I limiti "5/minute" sugli endpoint pubblici (vedi backend/rate_limit.py)
# sono pensati per un traffico reale, non per una suite di test che chiama
# lo stesso endpoint più volte in pochi secondi — disattivarlo qui evita
# fallimenti "flaky" (a intermittenza) dovuti all'ordine/velocità di
# esecuzione dei test, non a un vero bug.
limiter.enabled = False


@pytest.fixture(autouse=True)
def db_pulito():
    """
    Ricrea tutte le tabelle prima di OGNI test e le elimina subito dopo —
    "autouse=True" vuol dire che si applica automaticamente a ogni test di
    questo progetto, senza doverla richiedere esplicitamente ogni volta.
    Così ogni test parte da un database vuoto, senza dati lasciati da un
    test precedente che potrebbero falsare il risultato.
    """
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


_connect_originale = socket.socket.connect
_connect_ex_originale = socket.socket.connect_ex


def _solo_locale(indirizzo):
    """Solleva se la connessione esce dalla macchina; il loopback passa."""
    host = indirizzo[0] if isinstance(indirizzo, tuple) else indirizzo
    if host not in ("127.0.0.1", "::1", "localhost"):
        raise RuntimeError(
            f"i test non possono connettersi verso l'esterno ({host}): "
            "sostituisci la funzione che chiama il servizio"
        )


@pytest.fixture(autouse=True)
def rete_esterna_bloccata(monkeypatch):
    """
    Seconda rete: ogni connessione TCP passa da socket.socket.connect (o
    connect_ex), anche quelle di requests, httplib2 e ssl, che ne ereditano
    il metodo. Il loopback resta aperto perché su Windows il motore
    asincrono di TestClient comunica con sé stesso via 127.0.0.1:
    chiuderlo romperebbe tutta la suite.
    """
    def connect(sock, indirizzo):
        _solo_locale(indirizzo)
        return _connect_originale(sock, indirizzo)

    def connect_ex(sock, indirizzo):
        _solo_locale(indirizzo)
        return _connect_ex_originale(sock, indirizzo)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)


@pytest.fixture(autouse=True)
def integrazioni_esterne_finte(monkeypatch):
    """
    Sostituisce le funzioni che parlano con servizi esterni (Google
    Calendar, Gmail, Discord) con delle finte che non fanno nulla. Non sono
    la protezione (vedi il commento in cima al file), ma senza di loro ogni
    prenotazione dei test tenterebbe l'invio e riempirebbe il log di errori
    attesi. monkeypatch (fixture di pytest) annulla automaticamente ogni
    sostituzione a fine test, quindi non serve "ripristinare" nulla a mano.
    """
    import backend.routers.booking as booking_router
    import backend.routers.consulenza as consulenza_router
    import backend.routers.pacchetti_richieste as pacchetti_richieste_router

    monkeypatch.setattr(booking_router, "crea_evento_calendario", lambda **kwargs: None)
    monkeypatch.setattr(booking_router, "invia_conferma_cliente", lambda **kwargs: None)
    monkeypatch.setattr(booking_router, "invia_notifica_admin", lambda **kwargs: None)
    monkeypatch.setattr(booking_router, "invia_notifica_discord", lambda **kwargs: None)

    # Stessa cosa per consulenza.py e pacchetti_richieste.py: chiamano email
    # e Discord VERI tanto quanto booking.py, ma finora nessun test li
    # copriva — un test che li chiamasse senza queste righe manderebbe
    # davvero email/messaggi Discord con le credenziali reali del .env.
    monkeypatch.setattr(consulenza_router, "invia_conferma_richiesta_consulenza", lambda **kwargs: None)
    monkeypatch.setattr(consulenza_router, "invia_notifica_richiesta_consulenza_admin", lambda **kwargs: None)
    monkeypatch.setattr(consulenza_router, "invia_richiesta_consulenza_discord", lambda **kwargs: None)

    monkeypatch.setattr(pacchetti_richieste_router, "invia_conferma_richiesta_pacchetto", lambda **kwargs: None)
    monkeypatch.setattr(pacchetti_richieste_router, "invia_notifica_richiesta_pacchetto_admin", lambda **kwargs: None)
    monkeypatch.setattr(pacchetti_richieste_router, "invia_richiesta_pacchetto_discord", lambda **kwargs: None)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    """Sessione diretta al database di test, per preparare dati (slot, utenti...) senza passare dall'API."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


# ─── HELPER CONDIVISI DA PIÙ FILE DI TEST ─────────────────────
# Funzioni semplici (non fixture: prendono parametri, non ha senso
# iniettarle automaticamente) che diversi file di test ripetevano
# ciascuno per conto proprio in modo identico — vivono qui una volta sola,
# stesso principio delle fixture sopra.

def admin_headers():
    """Header Authorization con un token admin valido, per chiamare endpoint protetti da Depends(get_admin)."""
    return {"Authorization": f"Bearer {crea_token('admin')}"}


def studente_cookies(user_id, email):
    """
    Cookie di sessione studente valido, per chiamare endpoint protetti da
    Depends(get_studente)/get_studente_opzionale — dopo il passaggio a
    cookie httpOnly (vedi backend/routers/users.py), il token non si manda
    più come header Authorization ma come cookie "student_token", quindi
    va passato con cookies=studente_cookies(...) invece di
    headers={"Authorization": ...} nelle chiamate di TestClient.
    """
    return {"student_token": crea_token_studente(user_id, email)}


def crea_slot(db, start_time, duration_hours=1, is_available=True):
    """Crea uno Slot direttamente sul database di test, senza passare dall'endpoint POST /slots/ (che richiederebbe un admin)."""
    slot = Slot(start_time=start_time, duration_hours=duration_hours, is_available=is_available)
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return slot
