"""Model della tabella `bookings`: le prenotazioni.

Collega un `User` a uno `Slot` ed è il centro di quasi tutte le
funzionalità dell'applicazione.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    slot_id = Column(Integer, ForeignKey("slots.id"), nullable=False)

    # Valorizzato solo per le sessioni da 2 ore, che occupano due slot da
    # 1 ora consecutivi: il calendario genera esclusivamente slot da 1 ora.
    # Resta None per le prenotazioni da 1 ora.
    slot_id_secondario = Column(Integer, ForeignKey("slots.id"), nullable=True)

    duration_hours = Column(Integer, nullable=False, default=1)

    # Importi in centesimi: evita gli errori di arrotondamento dei float.
    # La divisione per 100 avviene solo in fase di visualizzazione.
    price_cents = Column(Integer, nullable=False)

    service_type = Column(String(30), nullable=False)  # vod_review, team_building, bo3_sparring, tournament_prep

    # Indicizzata perché filtrata da dashboard, analytics, job schedulati e
    # dal controllo sul numero di prenotazioni attive.
    status = Column(String(20), default="confirmed", index=True)  # confirmed, cancelled, no_show

    note_cliente = Column(Text, nullable=True)
    note_admin = Column(Text, nullable=True)  # riservate al coach, mai esposte allo studente

    vod_link = Column(String(500), nullable=True)
    replay_code = Column(String(200), nullable=True)
    calendar_event_id = Column(String(200), nullable=True)
    reminder_sent = Column(Boolean, default=False, nullable=False)

    # Valorizzato se la sessione è stata pagata scalando un credito da un
    # pacchetto anziché al prezzo di listino.
    package_id = Column(Integer, ForeignKey("packages.id"), nullable=True)

    # Token casuale che autentica il link pubblico di recensione inviato via
    # email dopo la sessione, senza richiedere un login.
    review_token = Column(String(64), nullable=True, unique=True)
    review_email_sent = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=func.now())

    user = relationship("User", backref="bookings")

    # `foreign_keys` esplicito perché due colonne puntano a `slots`: senza,
    # SQLAlchemy non può risolvere l'ambiguità. Per lo stesso motivo, nelle
    # query va usato `.join(Booking.slot)` e non `.join(Slot)`.
    slot = relationship("Slot", foreign_keys=[slot_id], backref="booking")
    slot_secondario = relationship("Slot", foreign_keys=[slot_id_secondario])

    package = relationship("Package", backref="bookings")
