# Rappresenta una prenotazione vera e propria — collega uno User (chi
# prenota) a uno Slot (quando). È il model più importante del progetto,
# perché quasi ogni funzionalità dell'app ruota attorno a questa tabella.

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)

    # ForeignKey("users.id") è il modo in cui SQLAlchemy (e i database
    # relazionali in generale) rappresentano un "collegamento" tra tabelle:
    # questa colonna contiene l'id di una riga della tabella "users". È
    # l'equivalente di dire "questa prenotazione appartiene a questo
    # utente". Il database stesso rifiuta di salvare un user_id che non
    # corrisponde a nessun utente esistente — un'altra protezione "a
    # livello di dati", come lo unique=True che hai visto in users.py.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    slot_id = Column(Integer, ForeignKey("slots.id"), nullable=False)

    duration_hours = Column(Integer, nullable=False, default=1)
    price_cents = Column(Integer, nullable=False)  # prezzo in centesimi (es. 3500 = €35)
    # Perché i centesimi e non gli euro con la virgola? Perché i numeri
    # decimali (float) in un computer non sono sempre precisi al centesimo
    # esatto (è un limite di come i float sono rappresentati in memoria) —
    # per i soldi si usano quasi sempre numeri interi nell'unità più
    # piccola possibile (i centesimi), e si divide per 100 solo quando si
    # deve MOSTRARE il prezzo a un umano.

    service_type = Column(String(30), nullable=False)  # vod_review, team_building, bo3_sparring, mentality_prep
    status = Column(String(20), default="confirmed")  # confirmed, cancelled, no_show

    note_cliente = Column(Text, nullable=True)
    note_admin = Column(Text, nullable=True)
    # Text invece di String(...): String ha una lunghezza massima definita
    # in anticipo, Text è pensato per testo libero potenzialmente lungo
    # (una nota puà essere un paio di frasi, non ha senso limitarla a priori).

    vod_link = Column(String(500), nullable=True)
    replay_code = Column(String(200), nullable=True)
    calendar_event_id = Column(String(200), nullable=True)  # id dell'evento creato su Google Calendar
    reminder_sent = Column(Boolean, default=False, nullable=False)  # promemoria pre-sessione già inviato

    created_at = Column(DateTime, default=func.now())

    # relationship() è diverso da Column(): non crea una colonna nel
    # database, è "zucchero sintattico" che ti permette di scrivere
    # prenotazione.user per ottenere direttamente l'oggetto User collegato
    # (invece di dover fare tu una query separata con lo user_id). SQLAlchemy
    # esegue quella query automaticamente al bisogno, dietro le quinte.
    #
    # backref="bookings" fa il collegamento anche nell'altro verso: grazie a
    # questa riga, un oggetto User ottiene "gratis" un attributo
    # utente.bookings con la lista di tutte le sue prenotazioni, anche se
    # questo attributo non è scritto da nessuna parte nel model User.
    user = relationship("User", backref="bookings")
    slot = relationship("Slot", backref="booking")
