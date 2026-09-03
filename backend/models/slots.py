"""Model della tabella `slots`: gli orari resi disponibili dal coach.

Uno slot è la possibilità di prenotare, non una prenotazione.
"""

from sqlalchemy import Column, Integer, DateTime, Boolean
from sqlalchemy.sql import func
from backend.database import Base


class Slot(Base):
    __tablename__ = "slots"

    id = Column(Integer, primary_key=True, index=True)

    # Sempre UTC naive: la colonna non porta il fuso, ma il valore va letto
    # come UTC ovunque nel progetto. La conversione a ora italiana è
    # responsabilità del livello di presentazione.
    #
    # Indicizzata perché è la colonna più filtrata e ordinata dell'app
    # (ricerca slot pubblica, job schedulati, liste admin) su una tabella
    # che cresce in continuazione.
    start_time = Column(DateTime, nullable=False, index=True)

    duration_hours = Column(Integer, nullable=False, default=1)

    is_available = Column(Boolean, default=True)

    # Quando is_available è False, questi due flag ne distinguono il motivo:
    # entrambi False = prenotato da un cliente; blocked_external = sovrapposto
    # a un evento del Google Calendar del coach; blocked_admin = bloccato a
    # mano (ferie). Il pannello admin mostra un'etichetta diversa per ognuno.
    blocked_external = Column(Boolean, default=False, nullable=False)
    blocked_admin = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=func.now())
