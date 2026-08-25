# Questo file è la "configurazione" di Alembic, lo strumento che gestisce
# le migrazioni del database (i file dentro alembic/versions/). Non lo
# tocchi quasi mai nell'uso quotidiano — è più che altro "impianto
# idraulico": collega Alembic ai tuoi model SQLAlchemy e decide come
# connettersi davvero al database quando esegui un comando tipo
# "alembic upgrade head".
#
# Perché servono le migrazioni? Perché SQLAlchemy da solo sa CREARE tutte
# le tabelle da zero (a partire dai model), ma non sa MODIFICARE una
# tabella che esiste già senza perdere i dati che contiene — "aggiungi una
# colonna a una tabella che ha già 1000 righe" è un'operazione diversa da
# "crea una tabella nuova". Alembic tiene una cronologia di questi
# cambiamenti incrementali, un po' come Git tiene la cronologia dei
# cambiamenti al codice: ogni file in alembic/versions/ è "un commit" del
# database.

import logging
from logging.config import fileConfig
from sqlalchemy import engine_from_config

# Questo import è più importante di quanto sembri: anche se User, Slot,
# Booking... non vengono mai usati per nome più sotto in questo file, il
# solo fatto di importarli fa sì che Python esegua quelle classi — ed è
# proprio eseguendole che SQLAlchemy "scopre" che tabelle esistono e le
# registra dentro Base.metadata. Senza questo import, Alembic non saprebbe
# nulla dei nostri model.
from backend.models import User, Slot, Booking, ClientNote, AvailabilityRule, AvailabilityException
from backend.database import Base
# target_metadata è la "fotografia" di come DOVREBBERO essere le tabelle,
# secondo il codice Python attuale — Alembic la confronta con lo stato vero
# del database quando generiamo una migrazione con "alembic revision
# --autogenerate" (usato per le modifiche di schema più meccaniche, es.
# aggiungere una colonna o un indice); per cambiamenti più delicati si
# scrive comunque la migrazione a mano.
target_metadata = Base.metadata

from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
#
# ATTENZIONE: fileConfig() riconfigura il logger ROOT, non solo quello di
# Alembic — se chiamato quando l'app (backend/main.py) ha già impostato il
# proprio formato di log PRIMA di eseguire le migrazioni (run_migrations()
# gira all'avvio, prima di qualunque richiesta), questa riga lo
# sovrascriverebbe silenziosamente con il formato di alembic.ini per il
# resto della vita del processo — un bug reale, scoperto proprio così.
# hasHandlers() è vero quando qualcun altro (la nostra app) ha già
# configurato il logging: in quel caso saltiamo fileConfig() invece di
# scavalcarlo. Quando Alembic gira da riga di comando (es. "alembic
# upgrade head" da terminale, non dentro l'app), il root logger non ha
# ancora handler, quindi fileConfig() si comporta come sempre.
if config.config_file_name is not None and not logging.getLogger().hasHandlers():
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # La modalità "offline" non si collega mai a un database vero: si
    # limita a STAMPARE le istruzioni SQL che verrebbero eseguite, utile se
    # per esempio volessi dare quel testo SQL a un DBA che gestisce il
    # database senza darti accesso diretto. In questo progetto non viene
    # mai usata nella pratica (si usa sempre "alembic upgrade head" in
    # modalità online, quella sotto), ma resta come funzionalità standard
    # di ogni progetto Alembic.
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Questa è la modalità DAVVERO usata da questo progetto: si collega al
    # database vero e applica le migrazioni sul serio.
    import os
    from dotenv import load_dotenv
    load_dotenv()

    # Stesso pattern già visto in backend/database.py: leggiamo
    # DATABASE_URL dall'ambiente, e se manca facciamo fallire subito con un
    # messaggio chiaro, invece di lasciare che Alembic provi a connettersi
    # a un indirizzo vuoto o sbagliato.
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is required")

    # config.get_section(...) legge le altre impostazioni da alembic.ini
    # (quelle non legate alla URL, che qui sovrascriviamo comunque con il
    # valore letto da .env). engine_from_config costruisce un "Engine"
    # SQLAlchemy, lo stesso concetto visto in backend/database.py — qui
    # però NullPool dice "non tenere connessioni aperte in un pool": ha
    # senso per uno script che gira una volta sola e poi termina, a
    # differenza del server web che invece resta acceso e beneficia di
    # riusare le connessioni.
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = database_url
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )
        # "with context.begin_transaction()" fa sì che tutte le modifiche di
        # questa esecuzione (anche se la migrazione contiene più passaggi)
        # vengano applicate come un blocco unico: o vanno a buon fine tutte,
        # o (in caso di errore a metà strada) nessuna viene applicata —
        # evita di lasciare il database in uno stato "a metà".
        with context.begin_transaction():
            context.run_migrations()


# Punto di ingresso del file: quando esegui "alembic upgrade head" (o
# qualunque altro comando Alembic), questo file viene eseguito, e questa
# ultima riga decide quale delle due modalità usare in base a come Alembic
# è stato invocato.
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
