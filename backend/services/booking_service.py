"""Effetti collaterali della cancellazione di una prenotazione.

Condivisi fra la cancellazione da pannello admin e quella self-service
dello studente, che devono comportarsi in modo identico.
"""

from sqlalchemy import update
from sqlalchemy.orm import Session
from backend.models.booking import Booking
from backend.models.package import Package
from backend.models.slots import Slot
from backend.services.calendar_service import elimina_evento_calendario


def libera_slot_prenotazione(prenotazione: Booking, db: Session):
    """Elimina l'evento su Google Calendar e rende di nuovo liberi gli slot.

    Gestisce anche lo slot secondario delle sessioni da 2 ore. Non esegue
    il commit: lo fa il chiamante, insieme al cambio di stato della
    prenotazione, così le due modifiche restano nella stessa transazione.
    """
    if prenotazione.calendar_event_id:
        # L'id si dimentica solo se Google conferma. Se la cancellazione non
        # riesce, l'evento resta sull'agenda del coach e questo id è l'unico
        # riferimento per ritrovarlo: azzerarlo comunque significherebbe
        # lasciare un appuntamento fantasma rimovibile solo cercandolo a mano
        # sul calendario. Non è una coda di ritentativi — subito dopo questa
        # chiamata la prenotazione passa a cancelled e nessun percorso
        # ripassa di qui — ma una traccia per la rimozione manuale.
        if elimina_evento_calendario(prenotazione.calendar_event_id):
            prenotazione.calendar_event_id = None

    # Gli slot tornano liberi in ogni caso, anche con Google irraggiungibile:
    # sono due fatti separati, e un guasto esterno non deve togliere dalla
    # vendita un'ora che il cliente ha appena liberato.
    slot = db.query(Slot).filter(Slot.id == prenotazione.slot_id).first()
    if slot:
        slot.is_available = True

    if prenotazione.slot_id_secondario:
        slot_secondario = db.query(Slot).filter(Slot.id == prenotazione.slot_id_secondario).first()
        if slot_secondario:
            slot_secondario.is_available = True


def restituisci_credito_pacchetto(prenotazione: Booking, db: Session):
    """Rimette nel pacchetto la sessione di una prenotazione confermata che si cancella.

    Da chiamare solo se la prenotazione era confirmed (decisione P7): il
    no-show consuma il credito anche se il coach in seguito lo cambia in
    cancelled. Così resta vera la regola sessioni_usate = prenotazioni del
    pacchetto confermate o no-show. Come libera_slot_prenotazione, non
    esegue il commit.
    """
    if prenotazione.package_id is None:
        return

    # "-1 sul valore vero" in un solo UPDATE, non lettura e poi scrittura:
    # una prenotazione concorrente sullo stesso pacchetto potrebbe aver appena
    # cambiato il contatore (vedi la riserva del credito in create_booking).
    # "> 0" è una guardia: un contatore che scendesse sotto zero regalerebbe
    # una sessione.
    db.execute(
        update(Package)
        .where(Package.id == prenotazione.package_id, Package.sessioni_usate > 0)
        .values(sessioni_usate=Package.sessioni_usate - 1)
    )
