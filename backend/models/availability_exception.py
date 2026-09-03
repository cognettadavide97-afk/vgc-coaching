"""Model della tabella `availability_exceptions`: i blocchi eccezionali.

A differenza di `AvailabilityRule`, che genera slot nuovi, questo model
serve a rendere non disponibili gli slot già esistenti in un periodo.
"""

from sqlalchemy import Column, Integer, Date, String, DateTime
from sqlalchemy.sql import func
from backend.database import Base


class AvailabilityException(Base):
    __tablename__ = "availability_exceptions"

    id = Column(Integer, primary_key=True, index=True)

    # Date e non DateTime: un blocco copre giorni interi. Le date sono
    # giorni solari italiani ed entrambi gli estremi sono inclusi.
    data_inizio = Column(Date, nullable=False)
    data_fine = Column(Date, nullable=False)

    motivo = Column(String(200), nullable=True)  # uso interno del coach
    created_at = Column(DateTime, default=func.now())
