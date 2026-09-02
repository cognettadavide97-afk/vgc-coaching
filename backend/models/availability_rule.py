# Rappresenta una regola di disponibilità RICORRENTE (es. "ogni martedì
# dalle 18 alle 22, in slot da 1 ora"), non gli slot veri e propri: quelli
# vengono generati a parte (vedi backend/services/availability_service.py)
# a partire da questa regola. È la differenza tra "la regola" e "i risultati
# della regola" — un po' come una ricetta non è lo stesso oggetto della
# torta che produce.

from sqlalchemy import Column, Integer, Time, Boolean, DateTime
from sqlalchemy.sql import func
from backend.database import Base


class AvailabilityRule(Base):
    __tablename__ = "availability_rules"

    id = Column(Integer, primary_key=True, index=True)

    # Salviamo il giorno della settimana come numero (0=lunedì ... 6=domenica)
    # invece che come testo ("lunedì") perché è lo stesso schema di numerazione
    # che usa il metodo .weekday() degli oggetti date/datetime di Python —
    # così il codice che genera gli slot (availability_service.py) può
    # confrontare direttamente regola.giorno_settimana con oggi.weekday()
    # senza dover tradurre avanti e indietro tra testo e numero.
    giorno_settimana = Column(Integer, nullable=False)

    # Time è un tipo diverso da DateTime: rappresenta SOLO un orario (es.
    # "18:00"), senza nessuna data attaccata — ha senso qui perché la regola
    # è "ogni martedì alle 18", non "martedì 12 agosto alle 18". Questi
    # orari sono sempre intesi come ora italiana (Europe/Rome): la
    # conversione in UTC avviene solo quando si genera un vero Slot.
    ora_inizio = Column(Time, nullable=False)
    ora_fine = Column(Time, nullable=False)

    durata_slot_ore = Column(Integer, nullable=False, default=1)

    # attiva permette di "disattivare" una regola senza cancellarla. È usata
    # davvero: il job notturno genera_slot_giornaliero (backend/scheduler.py)
    # genera slot SOLO dalle regole con attiva=True, quindi metterla a False
    # ferma la produzione di nuovi slot senza toccare quelli già creati.
    # Nota però che oggi nessun endpoint permette di cambiare questo campo:
    # una regola nasce attiva (default sotto) e per sospenderla servirebbe
    # intervenire a mano sul database.
    attiva = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=func.now())
