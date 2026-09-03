"""Entrypoint dell'applicazione: costruisce l'app FastAPI e la avvia.

Il modulo lavora in due fasi distinte:

1. **All'import** — configura il logging, crea `app`, registra rate limiter
   e CORS, monta i router e i file statici.
2. **All'avvio del server** — l'handler `lifespan` applica le migrazioni e
   fa partire lo scheduler.

La separazione è deliberata: importare questo modulo (come fanno i test)
non deve produrre alcun effetto collaterale su database o servizi esterni.
"""

import os
import logging
from contextlib import asynccontextmanager

# Il logging va configurato prima di importare i moduli del progetto: ogni
# modulo richiede il proprio logger all'import, e basicConfig ha effetto
# solo se chiamata prima del primo messaggio emesso.
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.rate_limit import limiter
from backend.scheduler import avvia_scheduler

import backend.routers.slots as slots
import backend.routers.booking as bookings
import backend.routers.users as users
import backend.routers.admin as admin
import backend.routers.discord_auth as discord_auth
import backend.routers.consulenza as consulenza
import backend.routers.pacchetti_richieste as pacchetti_richieste

from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from backend.database import engine, get_db
from backend.services.discord_service import invia_alert_sistema
from backend.services.backup_service import esegui_backup_database

logger = logging.getLogger(__name__)


def _migrazioni_in_sospeso(alembic_cfg) -> bool:
    """Indica se il database è indietro rispetto all'ultima migrazione scritta.

    Serve a decidere se vale la pena fare un backup preventivo: la maggior
    parte dei riavvii non comporta alcuna migrazione, e un backup a ogni
    avvio accumulerebbe copie identiche senza alcun beneficio.
    """
    script = ScriptDirectory.from_config(alembic_cfg)
    with engine.connect() as connessione:
        contesto = MigrationContext.configure(connessione)
        revisione_attuale = contesto.get_current_revision()
    return revisione_attuale != script.get_current_head()


def run_migrations():
    """Allinea lo schema del database all'ultima revisione Alembic.

    Se ci sono migrazioni in sospeso tenta prima un backup, ma un backup
    fallito o non configurato non blocca la migrazione: impedire ogni futuro
    aggiornamento dello schema finché Drive non è configurato sarebbe un
    problema peggiore di quello che si vuole prevenire.

    Un errore qui non interrompe l'avvio dell'app: viene registrato e
    notificato su Discord. È una scelta deliberata — un'app che parte con
    una funzionalità rotta è preferibile a un servizio che non parte
    affatto — ma significa che il problema può manifestarsi più tardi, con
    un errore meno leggibile, al primo utilizzo della funzione interessata.
    """
    try:
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            alembic_cfg = Config("alembic.ini")
            alembic_cfg.set_main_option("sqlalchemy.url", database_url)

            if _migrazioni_in_sospeso(alembic_cfg):
                logger.info("Migrazioni in sospeso: eseguo un backup di sicurezza prima di applicarle")
                if not esegui_backup_database(engine):
                    logger.warning("Backup pre-migrazione non riuscito (o non configurato) — procedo comunque")

            command.upgrade(alembic_cfg, "head")
            logger.info("Migrazioni eseguite con successo")
        else:
            logger.warning("DATABASE_URL non trovata — salto migrazioni")
    except Exception as e:
        logger.exception("Errore migrazioni")
        invia_alert_sistema(
            "Migrazione database fallita all'avvio",
            f"L'app è comunque partita, ma il database potrebbe non essere "
            f"aggiornato all'ultima versione attesa dal codice — alcune "
            f"funzionalità nuove potrebbero non funzionare. Dettaglio: {e}"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo di vita dell'app: migrazioni e scheduler all'avvio, stop alla chiusura.

    Il codice prima dello `yield` gira quando il server parte davvero, quello
    dopo quando si ferma. Tenere qui questi due passaggi — invece che a
    livello di modulo — è ciò che rende l'import privo di effetti
    collaterali: `TestClient`, se non usato come context manager, non innesca
    il lifespan, quindi la suite di test non tocca database né servizi reali.
    """
    run_migrations()
    scheduler = avvia_scheduler()

    yield

    scheduler.shutdown()


app = FastAPI(title="VGC Coaching API", version="1.0", lifespan=lifespan)

# Rate limiting: lo stato sull'app, l'handler per le risposte 429, il
# middleware che applica il controllo a ogni richiesta.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Frontend e API sono serviti dalla stessa origine, quindi le pagine dell'app
# non hanno bisogno di CORS permissivo: restringere impedisce a un altro sito
# di chiamare l'API dal browser di un visitatore. Le origini restano
# configurabili per gestire ambienti diversi.
FRONTEND_ORIGINS = os.getenv(
    "FRONTEND_ORIGINS",
    "http://127.0.0.1:8000,http://localhost:8000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(slots.router)
app.include_router(bookings.router)
app.include_router(users.router)
app.include_router(admin.router)
app.include_router(discord_auth.router)
app.include_router(consulenza.router)
app.include_router(pacchetti_richieste.router)

# Espone frontend/ sotto /static: le pagine HTML caricano da qui CSS e JS.
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/health")
def health(db: Session = Depends(get_db)):
    """Health check per il monitoraggio esterno.

    Esegue una query minima sul database invece di rispondere sempre 200: un
    processo vivo ma con il database irraggiungibile è comunque un servizio
    fuori uso, e senza questo controllo il monitor non se ne accorgerebbe.
    """
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/")
def root():
    return FileResponse("frontend/index.html")

@app.get("/about")
def about():
    return FileResponse("frontend/about.html")

@app.get("/privacy")
def privacy():
    return FileResponse("frontend/privacy.html")

@app.get("/admin-panel")
def admin_panel():
    return FileResponse("frontend/admin.html")
