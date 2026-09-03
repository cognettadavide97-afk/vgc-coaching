"""Model della tabella `users`: i clienti del servizio di coaching."""

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)

    # Il vincolo di unicità è a livello di database, non solo di codice:
    # regge anche in caso di richieste concorrenti. Il flusso di creazione
    # utente lo sfrutta come "get or create" invece di trattarlo come errore.
    email = Column(String(100), unique=True, nullable=False)

    telefono = Column(String(20), nullable=True)

    # Fascia di esperienza dichiarata dal cliente: junior / senior / master.
    categoria = Column(String(20), nullable=True)

    # Tag testuale digitato nel form. Modificabile dall'utente su Discord,
    # quindi non utilizzabile come identificativo stabile.
    discord_tag = Column(String(100), nullable=True)

    # Identificativo Discord permanente, popolato solo dal login OAuth2.
    # Vuoto per chi prenota come ospite.
    discord_id = Column(String(30), nullable=True, unique=True)

    created_at = Column(DateTime, default=func.now())

    # Valorizzata dal job di data retention quando anonimizza un cliente
    # inattivo. È il marcatore su cui il job riconosce i record già
    # processati: dedurlo dal formato dell'email sarebbe fragile.
    anonimizzato_at = Column(DateTime, nullable=True)
