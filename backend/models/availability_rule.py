"""Model della tabella `availability_rules`: la disponibilità ricorrente.

Descrive una regola ("ogni martedì 18-22, ore da 1 ora"): le ore che
produce si calcolano a ogni richiesta in `services/disponibilita_service.py`.
Fino al pezzo 4.6a la regola generava invece slot salvati in anticipo.
"""

from sqlalchemy import Column, Integer, Time, Boolean, DateTime
from backend.database import Base
from backend.services.timezone_service import ora_utc_naive


class AvailabilityRule(Base):
    __tablename__ = "availability_rules"

    id = Column(Integer, primary_key=True, index=True)

    # 0=lunedì ... 6=domenica, la stessa numerazione di `date.weekday()`:
    # permette il confronto diretto senza conversioni.
    giorno_settimana = Column(Integer, nullable=False)

    # Orari senza data, intesi come ora italiana. La conversione in UTC
    # avviene nel calcolo, ora per ora con il fuso di Roma.
    ora_inizio = Column(Time, nullable=False)
    ora_fine = Column(Time, nullable=False)

    durata_slot_ore = Column(Integer, nullable=False, default=1)

    # Il calcolo usa solo le regole attive, quindi metterla a False sospende
    # la regola senza eliminarla. Nessun endpoint espone oggi la modifica di
    # questo campo: una regola nasce attiva e per sospenderla serve
    # intervenire sul database (decisione P6b).
    attiva = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=ora_utc_naive)
