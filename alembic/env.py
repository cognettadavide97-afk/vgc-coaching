"""Configurazione di Alembic: collega le migrazioni ai model e al database.

Raramente da modificare. Definisce i metadati usati per l'autogenerazione
e come stabilire la connessione quando si esegue un comando Alembic.
"""

import logging
from logging.config import fileConfig
from sqlalchemy import engine_from_config

# Import necessario anche se i nomi non vengono usati: è l'esecuzione delle
# classi a registrare le tabelle in Base.metadata. Senza, Alembic non
# vedrebbe alcun model.
from backend.models import User, Slot, Booking, ClientNote, AvailabilityRule, AvailabilityException
from backend.database import Base
# Schema atteso secondo il codice: Alembic lo confronta con il database
# reale in fase di autogenerazione. Le migrazioni delicate restano scritte
# a mano.
target_metadata = Base.metadata

from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
#
# ATTENZIONE: fileConfig() riconfigura il logger root, non solo quello di
# Alembic. Le migrazioni girano anche all'avvio dell'applicazione, che ha
# già configurato il logging: senza questa guardia il formato dell'app
# verrebbe sostituito silenziosamente per il resto della vita del processo.
# Da riga di comando il root logger non ha handler e il comportamento resta
# quello predefinito.
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
    # Non usata da questo progetto: emette l'SQL invece di eseguirlo, utile
    # quando le migrazioni vanno consegnate a chi amministra il database.
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
    # Modalità effettivamente in uso.
    import os
    from dotenv import load_dotenv
    load_dotenv()

    # Fallimento esplicito invece di un tentativo di connessione verso un
    # indirizzo vuoto.
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is required")

    # La URL da ambiente sovrascrive quella di alembic.ini. NullPool perché
    # le migrazioni sono un'esecuzione singola: un pool di connessioni
    # riutilizzabili non porterebbe alcun vantaggio.
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
        # Transazione unica: un errore a metà non lascia lo schema in uno
        # stato intermedio.
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
