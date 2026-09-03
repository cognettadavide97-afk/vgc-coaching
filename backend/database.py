"""Configurazione della connessione al database e sessione per richiesta.

Espone i tre elementi usati dal resto del progetto: `engine` (il pool di
connessioni), `SessionLocal` (la fabbrica di sessioni) e `Base` (la classe
da cui ereditano tutti i model).
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Fallimento esplicito all'avvio: senza questo controllo l'assenza della
    # variabile emergerebbe molto più tardi, come errore di connessione in
    # un punto qualsiasi del codice.
    raise RuntimeError("DATABASE_URL environment variable is required")

# pool_pre_ping verifica che la connessione presa dal pool sia ancora viva
# prima di consegnarla. Senza, la prima richiesta dopo un periodo di
# inattività fallisce quando il server MySQL ha già chiuso la connessione
# per timeout.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency FastAPI: fornisce una sessione e ne garantisce la chiusura.

    Usata come `db: Session = Depends(get_db)` negli endpoint. Il `finally`
    viene eseguito anche quando l'endpoint solleva un'eccezione, quindi la
    connessione torna al pool in ogni caso.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
