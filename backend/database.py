# Questo file ha un solo compito: preparare il "collegamento" con il database
# MySQL, e offrire a tutto il resto del programma un modo standard e sicuro
# per usarlo. Ogni altro file che deve leggere o scrivere dati (i router,
# i model...) importa qualcosa da qui, invece di aprire connessioni proprie.

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# load_dotenv() legge il file .env nella root del progetto e "inietta" ogni
# riga (tipo DATABASE_URL=...) nelle variabili d'ambiente del processo, come
# se le avessi impostate a mano nel terminale. Senza questa riga, os.getenv()
# qui sotto non troverebbe nulla: il file .env da solo non fa nulla, va letto.
load_dotenv()

# os.getenv("DATABASE_URL") legge la variabile d'ambiente DATABASE_URL.
# Se non esiste, restituisce None invece di dare errore — per questo il
# controllo subito sotto è necessario: preferiamo far fallire l'app subito
# e con un messaggio chiaro, piuttosto che scoprire il problema più tardi
# con un errore criptico quando qualcuno prova a usare il database.
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required")

# create_engine() non apre subito una connessione al database: crea un
# oggetto "fabbrica di connessioni" (l'Engine), che SQLAlchemy userà quando
# servirà davvero. Pensa a DATABASE_URL come all'indirizzo del database
# (tipo un URL: mysql+pymysql://utente:password@host/nome_database).
#
# pool_pre_ping=True: prima di darti una connessione dal pool, SQLAlchemy le
# manda un piccolo "sei ancora viva?" (un SELECT 1) e la scarta in
# automatico se non risponde, aprendone una nuova al posto suo. Senza
# questo, una connessione tenuta in pool più a lungo di quanto il database
# la lasci aperta (i database gestiti chiudono le connessioni inattive dopo
# un tot) fa fallire con un errore la PRIMA richiesta che prova a
# riusarla — tipicamente quella del primo cliente della giornata, dopo una
# notte senza traffico. Il costo di questo controllo (un SELECT 1 in più
# per connessione) è trascurabile rispetto al beneficio.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# sessionmaker() crea, a sua volta, una "fabbrica di Session". Una Session è
# l'oggetto che userai davvero per parlare col database (query, aggiungere
# righe, salvare...) — è l'equivalente, in SQLAlchemy, di una conversazione
# aperta col database. autocommit=False e autoflush=False vogliono dire:
# "non salvare nulla finché non chiamo esplicitamente db.commit()" — così
# abbiamo il controllo su quando i cambiamenti diventano definitivi.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base è una classe speciale di SQLAlchemy: ogni "model" del progetto (in
# backend/models/) eredita da questa classe. È così che SQLAlchemy sa quali
# classi Python rappresentano tabelle del database, e può collegarle tra loro.
Base = declarative_base()


def get_db():
    """
    Questa funzione è una "dependency" di FastAPI: la vedrai usata così, in
    quasi ogni funzione dei router:

        def qualche_endpoint(db: Session = Depends(get_db)):
            ...

    FastAPI, prima di eseguire qualsiasi endpoint che la richiede, chiama
    get_db() al posto tuo e ti passa il risultato. Il trucco è la parola
    "yield" invece di "return": una funzione con yield è un generatore, cioè
    si "mette in pausa" al momento dello yield, restituisce il valore (la
    sessione db) a chi l'ha chiamata, e quando quella richiesta è finita
    (anche se è finita per colpa di un errore) riprende da dove si era
    fermata ed esegue il blocco "finally" — chiudendo sempre la connessione.
    Questo garantisce che nessuna connessione al database resti aperta per
    sbaglio, qualunque cosa succeda dentro l'endpoint.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
