from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import backend.routers.slots as slots
import backend.routers.booking as bookings
import backend.routers.users as users
import backend.routers.admin as admin
import os
from alembic.config import Config
from alembic import command

def run_migrations():
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

run_migrations()

app = FastAPI(title="VGC Coaching API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(slots.router)
app.include_router(bookings.router)
app.include_router(users.router)
app.include_router(admin.router)

app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
def root():
    return FileResponse("frontend/index.html")

@app.get("/admin-panel")
def admin_panel():
    return FileResponse("frontend/admin.html")

@app.get("/config/paypal-email")
def paypal_email():
    import os
    return {"email": os.getenv("PAYPAL_EMAIL", "")}