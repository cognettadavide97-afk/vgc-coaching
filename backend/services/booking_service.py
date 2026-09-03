"""Effetti collaterali della cancellazione di una prenotazione.

Condivisi fra la cancellazione da pannello admin e quella self-service
dello studente, che devono comportarsi in modo identico.
"""

from sqlalchemy.orm import Session
from backend.models.booking import Booking
from backend.models.slots import Slot
from backend.services.calendar_service import elimina_evento_calendario


def libera_slot_prenotazione(prenotazione: Booking, db: Session):
    """Elimina l'evento su Google Calendar e rende di nuovo liberi gli slot.

    Gestisce anche lo slot secondario delle sessioni da 2 ore. Non esegue
    il commit: lo fa il chiamante, insieme al cambio di stato della
    prenotazione, così le due modifiche restano nella stessa transazione.
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
