"""Model della tabella `availability_rules`: la disponibilità ricorrente.

Descrive una regola ("ogni martedì 18-22, slot da 1 ora"); gli slot concreti
sono generati a partire da questa da `services/availability_service.py`.
"""

from sqlalchemy import Column, Integer, Time, Boolean, DateTime
from sqlalchemy.sql import func
from backend.database import Base


class AvailabilityRule(Base):
    __tablename__ = "availability_rules"

    id = Column(Integer, primary_key=True, index=True)

    # 0=lunedì ... 6=domenica, la stessa numerazione di `date.weekday()`:
    # permette il confronto diretto senza conversioni.
    giorno_settimana = Column(Integer, nullable=False)

    # Orari senza data, intesi come ora italiana. La conversione in UTC
    # avviene alla generazione dello slot.
    ora_inizio = Column(Time, nullable=False)
    ora_fine = Column(Time, nullable=False)

    durata_slot_ore = Column(Integer, nullable=False, default=1)

    # Il job notturno genera slot solo dalle regole attive, quindi metterla
    # a False sospende la produzione senza toccare gli slot già creati.
    # Nessun endpoint espone oggi la modifica di questo campo: una regola
    # nasce attiva e per sospenderla serve intervenire sul database.
    attiva = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=func.now())
