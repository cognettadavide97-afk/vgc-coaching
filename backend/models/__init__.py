# Questo file non contiene nessuna logica: serve solo a "raccogliere" in un
# unico posto tutti i model (le classi che rappresentano le tabelle del
# database) sparsi negli altri file di questa cartella. Grazie a questo
# file, altrove nel progetto puoi scrivere:
#
#     from backend.models import User, Slot
#
# invece di dover scrivere un import separato per ciascun model. È solo
# comodità organizzativa — non cambia nulla nel comportamento del programma.
#
# C'è però un motivo tecnico più sottile per cui questo file (o un suo
# equivalente) viene sempre importato da qualche parte prima di usare il
# database: SQLAlchemy scopre l'esistenza di una tabella solo quando la
# classe Python corrispondente viene effettivamente importata (eseguita)
# almeno una volta. Se un model non venisse mai importato da nessuna parte,
# SQLAlchemy non saprebbe che esiste, e alcune operazioni (come le
# migrazioni automatiche di Alembic) non lo vedrebbero.

from backend.models.users import User
from backend.models.slots import Slot
from backend.models.booking import Booking
from backend.models.client_note import ClientNote
from backend.models.availability_rule import AvailabilityRule
from backend.models.availability_exception import AvailabilityException
from backend.models.package import Package
from backend.models.review import Review
