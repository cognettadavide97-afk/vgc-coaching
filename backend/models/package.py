# Rappresenta un pacchetto di sessioni pre-pagato assegnato a un cliente
# (es. "Tournament Prep — 6 sessioni da 2 ore"). Il pagamento vero avviene
# fuori dall'app (come per le prenotazioni singole): l'admin crea questa
# riga solo DOPO aver ricevuto il pagamento, dal pannello admin. Da quel
# momento il cliente può "spendere" le sessioni residue prenotando slot
# senza pagare di nuovo (vedi package_id in backend/models/booking.py e la
# validazione in backend/routers/booking.py).

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base


class Package(Base):
    __tablename__ = "packages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # "intro" / "team" / "tour" — chiave del catalogo fisso in
    # backend/services/package_service.py, non testo libero: i contenuti e
    # i prezzi dei pacchetti sono decisi a monte, non personalizzabili al
    # momento dell'assegnazione.
    tipo = Column(String(20), nullable=False)

    sessioni_totali = Column(Integer, nullable=False)
    sessioni_usate = Column(Integer, nullable=False, default=0)
    # Tutti i pacchetti del catalogo attuale sono fatti di sessioni da 2 ore
    # (vedi il catalogo), ma teniamo il valore sulla riga invece che
    # hardcoded nella logica di redenzione, così un pacchetto già assegnato
    # resta valido anche se in futuro il catalogo cambiasse durata.
    durata_sessione_ore = Column(Integer, nullable=False, default=2)
    prezzo_cents = Column(Integer, nullable=False)  # prezzo scontato realmente pagato dal cliente

    created_at = Column(DateTime, default=func.now())

    user = relationship("User", backref="packages")
