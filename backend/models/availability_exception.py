"""Model della tabella `availability_exceptions`: i blocchi eccezionali.

A differenza di `AvailabilityRule`, che genera slot nuovi, questo model
serve a rendere non disponibili gli slot di un periodo: quelli che esistono
già alla sua creazione e quelli generati dopo, che nascono bloccati.
"""

from sqlalchemy import Column, Integer, Date, String, DateTime
from backend.database import Base
from backend.services.timezone_service import ora_utc_naive


class AvailabilityException(Base):
    __tablename__ = "availability_exceptions"

    id = Column(Integer, primary_key=True, index=True)

    # Date e non DateTime: un blocco copre giorni interi. Le date sono
    # giorni solari italiani ed entrambi gli estremi sono inclusi.
    data_inizio = Column(Date, nullable=False)
    data_fine = Column(Date, nullable=False)

    motivo = Column(String(200), nullable=True)  # uso interno del coach
    created_at = Column(DateTime, default=ora_utc_naive)
