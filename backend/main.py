# Questo è il punto di ingresso di TUTTO il programma. Quando lanci il
# comando "uvicorn backend.main:app", uvicorn (il server web) importa questo
# file, esegue tutto il codice a livello "modulo" (cioè non dentro nessuna
# funzione — quindi tutto qui sotto, dall'alto verso il basso, appena il file
# viene importato) e poi usa la variabile "app" per rispondere alle richieste
# che arrivano. Non c'è nessuna "funzione main()" da chiamare: in Python,
# il semplice fatto di importare questo file fa già partire tutto.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

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

import os
from alembic.config import Config
from alembic import command


def run_migrations():
    """
    Applica automaticamente a ogni avvio dell'app tutte le "migrazioni" del
    database non ancora eseguite (vedi la cartella alembic/versions/) — cioè
    porta la struttura del database MySQL allo stato più aggiornato previsto
    dal codice, senza bisogno di farlo manualmente ogni volta che si fa il
    deploy. command.upgrade(alembic_cfg, "head") vuol dire letteralmente
    "porta il database alla versione più recente" ("head" = la punta della
    cronologia delle migrazioni, come l'ultimo commit in un ramo Git).

    Il blocco try/except è deliberato: se le migrazioni falliscono, l'app
    continua comunque ad avviarsi (stampa solo un errore) invece di bloccarsi
    del tutto — utile in fase di sviluppo, ma vuol dire che un problema del
    database potrebbe manifestarsi più tardi con errori meno chiari quando
    qualcuno prova a usare una funzione che ne ha bisogno.
    """
    try:
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            alembic_cfg = Config("alembic.ini")
            alembic_cfg.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(alembic_cfg, "head")
            print("Migrazioni eseguite con successo")
        else:
            print("DATABASE_URL non trovata — salto migrazioni")
    except Exception as e:
        print(f"Errore migrazioni: {e}")


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
@app.get("/")
def root():
    return FileResponse("frontend/index.html")

@app.get("/about")
def about():
    return FileResponse("frontend/about.html")

@app.get("/admin-panel")
def admin_panel():
    return FileResponse("frontend/admin.html")
