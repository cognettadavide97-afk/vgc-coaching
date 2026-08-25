# Rappresenta un "orario disponibile" creato dal coach — non ancora una
# prenotazione, solo la possibilità di prenotarlo. Vedi backend/models/users.py
# per la spiegazione generale di cosa sia un model SQLAlchemy.

from sqlalchemy import Column, Integer, DateTime, Boolean
from sqlalchemy.sql import func
from backend.database import Base


class Slot(Base):
    __tablename__ = "slots"

    id = Column(Integer, primary_key=True, index=True)

    # ATTENZIONE, concetto importante: questo campo è "sempre UTC, naive".
    # "Naive" (in inglese "ingenuo") è il termine tecnico per un datetime che
    # NON porta con sé l'informazione del fuso orario — è solo una data e
    # un'ora, senza dire "rispetto a dove". Il progetto ha scelto una
    # convenzione precisa per evitare bug sui fusi orari: ovunque nel
    # database questo valore rappresenta sempre l'ora UTC, anche se la
    # colonna in sé non lo "sa". È compito del codice (vedi
    # backend/services/timezone_service.py) convertire da/verso l'ora
    # italiana solo quando serve mostrarla a un umano o quando arriva un
    # input dall'admin.
    # index=True: questa colonna è la più interrogata di tutto il progetto
    # (ogni ricerca di slot pubblica, ogni job schedulato, ogni pagina
    # admin la filtra e/o la ordina) — senza un indice, il database deve
    # scorrere l'intera tabella ad ogni query. Con poche centinaia di righe
    # non si nota, ma la tabella cresce ogni giorno senza pulizia (un nuovo
    # slot per ogni ora disponibile, per sempre), quindi il costo cresce
    # nel tempo mentre l'indice lo mantiene costante.
    start_time = Column(DateTime, nullable=False, index=True)

    duration_hours = Column(Integer, nullable=False, default=1)

    # Boolean è semplicemente vero/falso (come bool in Python). is_available
    # è il campo che rende uno slot "prenotabile o no". Nota che questo
    # unico campo True/False non basta a sapere PERCHÉ uno slot non è
    # disponibile — per questo esistono i due campi sotto.
    is_available = Column(Boolean, default=True)

    # Questi due campi Boolean servono a distinguere, quando is_available è
    # False, il MOTIVO: uno slot può essere non disponibile perché qualcuno
    # l'ha prenotato (nessuno dei due flag è True), perché si sovrappone a
    # un evento sul Google Calendar del coach (blocked_external), oppure
    # perché il coach l'ha bloccato a mano — es. per le ferie
    # (blocked_admin). Il pannello admin usa questa distinzione per mostrare
    # un'etichetta diversa ("Prenotato" / "Bloccato (calendario)" /
    # "Bloccato (ferie)") nella stessa colonna "Stato".
    blocked_external = Column(Boolean, default=False, nullable=False)
    blocked_admin = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=func.now())
