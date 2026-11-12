"""Definizione unica di incasso, letta da dashboard, analytics e lista clienti.

Incassato = sessioni singole svolte + pacchetti venduti (decisione P8):

- una sessione conta quando è avvenuta: confermata e con l'orario d'inizio
  passato. Una futura può ancora essere cancellata, una cancellata non è mai
  stata pagata, un no-show non si incassa;
- un pacchetto conta per intero alla data in cui l'amministratore lo
  assegna, perché lo assegna solo dopo averlo incassato (models/package.py).
  Le sessioni pagate col pacchetto hanno prezzo zero: non lo contano due volte.

Con tre definizioni separate i tre numeri raccontavano storie diverse (voce
57): la dashboard contava le sessioni future, la lista clienti anche le
cancellate e i no-show, nessuno i pacchetti.
"""

from datetime import datetime
from typing import List, NamedTuple, Optional
from sqlalchemy.orm import Session
from backend.models.booking import Booking
from backend.models.package import Package
from backend.models.slots import Slot
from backend.services.timezone_service import ora_utc_naive


class Movimento(NamedTuple):
    """Un incasso: quando (UTC naive, come nel database), da chi, quanto."""
    data_utc: datetime
    user_id: int
    cents: int


def movimenti_incasso(
    db: Session,
    dal_utc: Optional[datetime] = None,
    user_ids: Optional[List[int]] = None,
) -> List[Movimento]:
    """Tutti gli incassi, eventualmente dal `dal_utc` in poi o dei soli `user_ids`.

    Restituisce i movimenti e non una somma: ogni chiamante li raggruppa a
    modo suo (totale, per mese, per cliente) senza riscrivere la regola. Le
    somme si fanno quindi in Python: con due tabelle di origine la regola in
    SQL andrebbe ripetuta per ogni raggruppamento, e sui volumi di un coach
    leggere qualche riga in più non si misura.
    """
    sessioni = db.query(Slot.start_time, Booking.user_id, Booking.price_cents) \
        .select_from(Booking).join(Booking.slot).filter(
            Booking.status == "confirmed",
            Slot.start_time < ora_utc_naive()
        )
    pacchetti = db.query(Package.created_at, Package.user_id, Package.prezzo_cents)

    if dal_utc is not None:
        sessioni = sessioni.filter(Slot.start_time >= dal_utc)
        pacchetti = pacchetti.filter(Package.created_at >= dal_utc)
    if user_ids is not None:
        sessioni = sessioni.filter(Booking.user_id.in_(user_ids))
        pacchetti = pacchetti.filter(Package.user_id.in_(user_ids))

    return [Movimento(*riga) for riga in sessioni.all() + pacchetti.all()]
