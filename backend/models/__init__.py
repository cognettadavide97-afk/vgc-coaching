"""Raccoglie i model in un unico punto di import.

Oltre alla comodità di `from backend.models import User, Slot`, questo
modulo garantisce che tutte le classi vengano importate almeno una volta:
SQLAlchemy registra una tabella solo quando il model corrispondente è
stato eseguito, e Alembic non vedrebbe le tabelle mai importate.
"""

from backend.models.users import User
from backend.models.slots import Slot
from backend.models.booking import Booking
from backend.models.client_note import ClientNote
from backend.models.availability_rule import AvailabilityRule
from backend.models.availability_exception import AvailabilityException
from backend.models.package import Package
from backend.models.review import Review
