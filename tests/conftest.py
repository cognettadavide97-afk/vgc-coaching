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
# 2. Integrazioni esterne disattivate: i test non devono MAI mandare email
#    vere, messaggi Discord veri o creare eventi sul calendario Google vero,
#    anche se per errore le credenziali in .env fossero quelle reali (vedi
#    backend/routers/booking.py, che le chiama dentro create_booking) — le
#    sostituiamo con funzioni "finte" che non fanno nulla.

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.database import Base, get_db
import backend.models  # registra tutti i model su Base.metadata (vedi backend/models/__init__.py)
from backend.main import app
from backend.rate_limit import limiter
from backend.models.slots import Slot
from backend.services.auth_service import crea_token

TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
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


@pytest.fixture(autouse=True)
def integrazioni_esterne_finte(monkeypatch):
    """
    Sostituisce le funzioni che parlano con servizi esterni (Google
    Calendar, Gmail, Discord) con delle finte che non fanno nulla — vedi il
    commento in cima al file per il perché. monkeypatch (fixture di pytest)
    annulla automaticamente ogni sostituzione a fine test, quindi non serve
    "ripristinare" nulla a mano.
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


def crea_slot(db, start_time, duration_hours=1, is_available=True):
    """Crea uno Slot direttamente sul database di test, senza passare dall'endpoint POST /slots/ (che richiederebbe un admin)."""
    slot = Slot(start_time=start_time, duration_hours=duration_hours, is_available=is_available)
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return slot
