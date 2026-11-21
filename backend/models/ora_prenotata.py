"""Model della tabella `ore_prenotate`: le ore già vendute (pezzo 4.3b, P9).

Una riga per ogni ora occupata da una prenotazione non cancellata: una
sessione da 2 ore ne ha due. Serve solo a impedire che la stessa ora si
venda due volte, anche quando due richieste arrivano nello stesso istante.

Il controllo "è libera?" seguito dalla scrittura lascerebbe una finestra in
cui due richieste trovano l'ora ancora libera (race condition). Qui la
verifica la fa il database: `inizio` è la chiave primaria, quindi non
possono esistere due righe con la stessa ora, e la seconda scrittura viene
rifiutata. Oggi la stessa garanzia la dà la riserva sullo slot
(`routers/booking.py`); con la disponibilità calcolata gli slot spariscono e
resta questa. Il database può garantire "nessun doppione" solo dentro una
colonna: per questo una sessione da 2 ore occupa due righe e non una.

La guardia confronta inizi esatti: è completa perché ogni prenotazione
inizia all'ora piena (misurato in produzione il 2026-11-21: nessuno slot né
regola con minuti diversi da zero), condizione che dal pezzo 4.4 va
garantita da chi propone gli orari.
"""

from sqlalchemy import Column, Integer, DateTime, ForeignKey
from backend.database import Base


class OraPrenotata(Base):
    __tablename__ = "ore_prenotate"

    # UTC naive come ogni orario del database.
    inizio = Column(DateTime, primary_key=True)

    # ON DELETE CASCADE: se la prenotazione viene eliminata (diritto
    # all'oblio, routers/admin/clients.py) il database toglie anche le sue
    # ore. Senza, le righe di un no-show, che occupa ancora la sua ora,
    # bloccherebbero l'eliminazione con l'errore 1451 su MySQL.
    #
    # Nessuna relationship, di proposito: con una relationship da Booking
    # alle sue ore, alla cancellazione di una prenotazione l'ORM proverebbe
    # a scrivere NULL in booking_id delle righe collegate invece di lasciarle
    # al database, e la colonna è obbligatoria. Le righe si scrivono e si tolgono esplicitamente, in
    # create_booking e in libera_slot_prenotazione.
    booking_id = Column(
        Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True
    )
