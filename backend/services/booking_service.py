# Effetti collaterali della cancellazione di una prenotazione, condivisi
# tra due punti diversi del progetto: la cancellazione manuale
# dell'admin (PATCH /admin/prenotazioni/{id}/stato) e la cancellazione
# self-service del cliente loggato con Discord (PATCH /bookings/{id}/cancella,
# vedi backend/routers/booking.py) — stessa logica, per non ripeterla due volte.

from sqlalchemy.orm import Session
from backend.models.booking import Booking
from backend.models.slots import Slot
from backend.services.calendar_service import elimina_evento_calendario


def libera_slot_prenotazione(prenotazione: Booking, db: Session):
    """
    Elimina l'evento Google Calendar collegato (se esiste) e rimette
    disponibili lo slot — o i DUE slot, per una sessione da 2 ore che ne
    aveva uniti due (vedi slot_id_secondario in backend/models/booking.py
    e create_booking in backend/routers/booking.py per il perché).
    Non chiama db.commit() da sola: lo fa il chiamante, insieme al
    cambio di status della prenotazione stessa.
    """
    if prenotazione.calendar_event_id:
        elimina_evento_calendario(prenotazione.calendar_event_id)
        prenotazione.calendar_event_id = None

    slot = db.query(Slot).filter(Slot.id == prenotazione.slot_id).first()
    if slot:
        slot.is_available = True

    if prenotazione.slot_id_secondario:
        slot_secondario = db.query(Slot).filter(Slot.id == prenotazione.slot_id_secondario).first()
        if slot_secondario:
            slot_secondario.is_available = True
