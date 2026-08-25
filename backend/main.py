# Questo è il punto di ingresso di TUTTO il programma. Quando lanci il
# comando "uvicorn backend.main:app", uvicorn (il server web) importa questo
# file, esegue tutto il codice a livello "modulo" (cioè non dentro nessuna
# funzione — quindi tutto qui sotto, dall'alto verso il basso, appena il file
# viene importato) e poi usa la variabile "app" per rispondere alle richieste
# che arrivano. Non c'è nessuna "funzione main()" da chiamare: in Python,
# il semplice fatto di importare questo file fa già partire tutto.

import os
import logging

# Configurazione UNICA del logging per tutto il progetto: va fatta qui,
# prima di importare qualunque altro modulo del progetto (i router, i
# service...), perché ognuno di essi chiederà il proprio "logger con nome"
# (vedi il commento più sotto su logging.getLogger(__name__)) — basicConfig
# decide come TUTTI quei logger si comportano (livello minimo, formato del
# messaggio), ma ha effetto solo se chiamata prima che arrivi il primo
# messaggio di log. main.py è il primo file che viene eseguito quando parte
# l'app (vedi il commento in cima al file), quindi è il punto giusto.
#
# Sostituisce i vecchi print() sparsi in tutto il backend: un print() è solo
# testo su stdout, senza livello (non puoi filtrare "solo gli errori"), senza
# timestamp indipendente, e — soprattutto dentro un except — senza lo stack
# trace di dove l'errore è nato davvero. logging risolve tutti e tre questi
# problemi, restando comunque semplice: continua a scrivere su console (che
# su Railway diventa comunque log della piattaforma, come prima), solo in
# modo strutturato. LOG_LEVEL è configurabile da variabile d'ambiente (default
# INFO) per poter passare a DEBUG in caso di indagine su un problema, senza
# toccare il codice.
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"

# Nota per chi si stesse chiedendo perché non semplicemente
# "logging.basicConfig(...)" senza un nome a parte: Alembic, quando esegue
# le migrazioni (run_migrations() più sotto), interferirebbe con questa
# stessa configurazione chiamando al suo interno logging.config.fileConfig()
# sul proprio alembic.ini — un bug reale, scoperto proprio così, che
# silenziosamente sovrascriveva il nostro formato col suo per il resto della
# vita del processo. La soluzione vera è in alembic/env.py (salta
# fileConfig() se il root logger ha già handler configurati): con quella in
# posto, basta chiamare questa configurazione una volta sola, qui.
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

# slowapi è la libreria che implementa il "rate limiting": impedisce che
# qualcuno mandi troppe richieste di fila allo stesso indirizzo (protezione
# anti-bot/anti-abuso). Questi tre import servono per collegarla all'app.
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.rate_limit import limiter
from backend.scheduler import avvia_scheduler

# Ogni file dentro backend/routers/ definisce un gruppo di indirizzi web
# (endpoint) collegati tra loro. Qui li importiamo tutti, dando a ciascuno
# un nome breve (es. "as slots"), per poterli "attaccare" all'app più sotto.
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

# logger di questo modulo — vedi il commento sopra su logging.getLogger.
logger = logging.getLogger(__name__)


def _migrazioni_in_sospeso(alembic_cfg) -> bool:
    """
    True se il database è indietro rispetto all'ultima migrazione scritta
    nel codice (alembic/versions/) — confronta la revisione salvata nel
    database (tabella alembic_version) con quella più recente conosciuta
    da Alembic. Serve per decidere SE vale la pena fare un backup: farlo
    ad ogni riavvio, anche quando non c'è nessuna migrazione da applicare
    (il caso più comune — un riavvio non cambia lo schema), riempirebbe
    Drive di backup identici senza nessun beneficio.
    """
    script = ScriptDirectory.from_config(alembic_cfg)
    with engine.connect() as connessione:
        contesto = MigrationContext.configure(connessione)
        revisione_attuale = contesto.get_current_revision()
    return revisione_attuale != script.get_current_head()


def run_migrations():
    """
    Applica automaticamente a ogni avvio dell'app tutte le "migrazioni" del
    database non ancora eseguite (vedi la cartella alembic/versions/) — cioè
    porta la struttura del database MySQL allo stato più aggiornato previsto
    dal codice, senza bisogno di farlo manualmente ogni volta che si fa il
    deploy. command.upgrade(alembic_cfg, "head") vuol dire letteralmente
    "porta il database alla versione più recente" ("head" = la punta della
    cronologia delle migrazioni, come l'ultimo commit in un ramo Git).

    Se ci sono migrazioni da applicare, PRIMA tentiamo un backup di
    sicurezza (vedi backend/services/backup_service.py) — una migrazione
    scritta male è esattamente il tipo di errore da cui un backup dovrebbe
    proteggere, e il momento in cui serve di più è proprio un attimo prima
    che quella migrazione giri sul database reale. Un backup fallito o non
    ancora configurato (vedi il "if not" sotto) non blocca comunque la
    migrazione: bloccare per sempre ogni futura migrazione finché qualcuno
    non sistema Drive sarebbe un problema peggiore di procedere senza un
    backup fresco.

    Il blocco try/except è deliberato: se le migrazioni falliscono, l'app
    continua comunque ad avviarsi (registra solo un errore nei log) invece
    di bloccarsi del tutto — utile in fase di sviluppo, ma vuol dire che un
    problema del database potrebbe manifestarsi più tardi con errori meno
    chiari quando qualcuno prova a usare una funzione che ne ha bisogno.
    Per questo, oltre al log, avvisiamo subito il coach su Discord (vedi
    invia_alert_sistema in backend/services/discord_service.py): un deploy
    con una migrazione fallita è il tipo di problema che altrimenti si nota
    solo quando un cliente prova a usare la funzione nuova e trova un errore.
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
        # logger.exception() include automaticamente lo STACK TRACE completo
        # nel log — con un print() avresti solo il messaggio dell'eccezione,
        # non da dove è partita: per un errore di migrazione, sapere la riga
        # esatta fa la differenza tra capire subito il problema e dover
        # indagare. Teniamo comunque "as e": serve al messaggio Discord
        # qui sotto, che vuole un riassunto breve, non l'intero traceback.
        logger.exception("Errore migrazioni")
        invia_alert_sistema(
            "Migrazione database fallita all'avvio",
            f"L'app è comunque partita, ma il database potrebbe non essere "
            f"aggiornato all'ultima versione attesa dal codice — alcune "
            f"funzionalità nuove potrebbero non funzionare. Dettaglio: {e}"
        )


# Questa chiamata avviene SUBITO, appena il file viene importato — prima
# ancora che l'app esista. È voluto: vogliamo che il database sia aggiornato
# prima che qualunque richiesta possa arrivare.
run_migrations()

# Questa riga crea l'applicazione vera e propria. "app" è l'oggetto che
# uvicorn userà per rispondere a ogni richiesta HTTP in arrivo — è il "cuore"
# di FastAPI. title e version servono solo per la documentazione automatica
# che FastAPI genera da solo (visitabile su /docs quando il server è attivo).
app = FastAPI(title="VGC Coaching API", version="1.0")

# Queste tre righe collegano il rate limiter all'app:
# - app.state.limiter salva l'oggetto limiter dove FastAPI/slowapi se lo aspettano
# - add_exception_handler dice cosa rispondere quando qualcuno supera il limite
#   (verrà usato l'errore standard di slowapi: risposta 429 "Too Many Requests")
# - add_middleware attiva davvero il controllo su ogni richiesta
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS (Cross-Origin Resource Sharing) è la regola del browser che decide se
# una pagina web caricata da un sito può chiamare le API di un altro sito.
# L'app serve frontend e backend dallo stesso processo/origine, quindi le
# richieste della propria pagina non hanno bisogno di CORS aperto: restringere
# riduce la superficie d'attacco (nessun altro sito può chiamare l'API dal
# browser di un visitatore). Origini configurabili per gestire dev/produzione.
FRONTEND_ORIGINS = os.getenv(
    "FRONTEND_ORIGINS",
    "http://127.0.0.1:8000,http://localhost:8000"
).split(",")

# Un "middleware" è codice che FastAPI esegue automaticamente PRIMA (e a
# volte dopo) ogni singola richiesta, qualunque sia l'endpoint chiamato —
# utile per cose trasversali come sicurezza e logging, che non ha senso
# ripetere manualmente in ogni funzione.
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# include_router() "attacca" all'app tutti gli indirizzi definiti in ciascun
# file di backend/routers/. Prima di queste righe, quegli indirizzi esistono
# solo come codice Python: da qui in poi sono davvero raggiungibili da fuori
# (es. una richiesta a /bookings/ verrà gestita dal codice in booking.py).
app.include_router(slots.router)
app.include_router(bookings.router)
app.include_router(users.router)
app.include_router(admin.router)
app.include_router(discord_auth.router)
app.include_router(consulenza.router)
app.include_router(pacchetti_richieste.router)

# Avvia il job in background che controlla periodicamente se ci sono
# promemoria da inviare (vedi backend/scheduler.py). Da qui in poi gira per
# conto suo, senza bisogno che nessuno lo richiami.
avvia_scheduler()

# Da questa riga in poi, qualunque file dentro la cartella "frontend/" è
# raggiungibile dal browser con il prefisso /static/... — per esempio
# frontend/js/app.js diventa raggiungibile come /static/js/app.js. È così
# che le pagine HTML riescono a caricare il proprio CSS/JS.
app.mount("/static", StaticFiles(directory="frontend"), name="static")


# Queste funzioni sono normali endpoint FastAPI (esattamente come quelli
# nei router), ma invece di restituire dati JSON restituiscono un intero
# file HTML: FileResponse legge il file dal disco e lo manda al browser così
# com'è. Sono gli "indirizzi di ingresso" delle pagine web dell'app.
@app.get("/health")
def health(db: Session = Depends(get_db)):
    """
    Endpoint pensato per un servizio di monitoraggio esterno (es.
    UptimeRobot, Better Uptime — gratuiti, bastano pochi minuti di setup):
    fanno una richiesta periodica a questo indirizzo e avvisano il coach
    se smette di rispondere con 200. "SELECT 1" è la query più semplice
    possibile: non legge nessuna tabella vera, serve solo a controllare che
    la connessione al database risponda ancora — un processo "vivo" ma con
    il database irraggiungibile è comunque un sito rotto per chi lo visita,
    e senza questo controllo qui il monitoraggio esterno non se ne
    accorgerebbe (l'app risponderebbe comunque a una richiesta che non
    tocca il database).
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
