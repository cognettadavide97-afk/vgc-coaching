"""Model della tabella `packages`: i pacchetti di sessioni pre-pagati.

Il pagamento avviene fuori dall'applicazione: l'amministratore crea il
pacchetto solo dopo averlo incassato. Da quel momento il cliente può
spendere le sessioni residue prenotando a prezzo zero.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base


class Package(Base):
    __tablename__ = "packages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Chiave del catalogo fisso definito in services/package_service.py
    # ("intro", "team", "tour"), non testo libero: contenuti e prezzi sono
    # decisi a monte e non personalizzabili al momento dell'assegnazione.
    tipo = Column(String(20), nullable=False)

    sessioni_totali = Column(Integer, nullable=False)
    sessioni_usate = Column(Integer, nullable=False, default=0)

    # Duplicata dal catalogo al momento della creazione: un pacchetto già
    # venduto conserva le condizioni con cui è stato acquistato anche se il
    # catalogo cambia in seguito.
    durata_sessione_ore = Column(Integer, nullable=False, default=2)
    prezzo_cents = Column(Integer, nullable=False)

    created_at = Column(DateTime, default=func.now())

    user = relationship("User", backref="packages")
