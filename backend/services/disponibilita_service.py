"""Disponibilità calcolata: le ore prenotabili ricavate al momento (decisione P9).

Sostituirà la tabella `slots`, che è una copia della disponibilità scritta
in anticipo: ogni cambiamento della realtà (un impegno spostato su Google,
un blocco eliminato) andava ricopiato a mano o da un job, e finché non
succedeva la copia mentiva. Qui non si salva nulla: si parte dalle regole
ricorrenti e si tolgono blocchi, prenotazioni e impegni Google, ogni volta
che qualcuno chiede. Una sola fonte di verità, niente da tenere allineato.

Nel pezzo 4.2 la funzione esiste ma il sito non la usa ancora; le
prenotazioni puntano ancora a uno slot, da cui si legge il loro orario.
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from backend.models.availability_exception import AvailabilityException
from backend.models.availability_rule import AvailabilityRule
from backend.models.booking import Booking
from backend.models.slots import Slot
from backend.services.calendar_service import leggi_eventi_calendario
from backend.services.timezone_service import ROME_TZ, ora_utc_naive, utc_to_rome, intervalli_si_sovrappongono

UN_ORA = timedelta(hours=1)


def _ore_della_regola(regola: AvailabilityRule, giorno) -> list[datetime]:
    """Gli inizi da 1 ora della regola in quel giorno, convertiti in UTC naive.

    La regola è in ora italiana: la conversione si fa ora per ora con il
    fuso di Roma, così l'ora legale sposta l'orario UTC e non quello che
    vede il cliente.
    """
    ore = []
    cursore = datetime.combine(giorno, regola.ora_inizio)
    fine_finestra = datetime.combine(giorno, regola.ora_fine)
    while cursore + UN_ORA <= fine_finestra:
        ore.append(cursore.replace(tzinfo=ROME_TZ).astimezone(timezone.utc).replace(tzinfo=None))
        cursore += UN_ORA
    return ore


def calcola_disponibilita(db: Session, da: datetime, a: datetime) -> dict[int, list[datetime]]:
    """Gli inizi prenotabili fra `da` e `a` (UTC naive), per durata in ore.

    Restituisce {1: [...], 2: [...]}, liste ordinate di inizi in UTC naive.
    Un'ora è prenotabile se una regola attiva la prevede, è futura, il suo
    giorno non è bloccato e non si sovrappone né a una prenotazione non
    cancellata né a un impegno Google.

    Una sessione da 2 ore parte ogni 2 ore dall'inizio della regola (15-19
    offre 15 e 17, 18-22 offre 18 e 20), se entrambe le ore sono libere.
    Partire a metà (16-18) lascerebbe isolate le ore ai lati, difficili da
    vendere: è il motivo dei vecchi orari fissi 15 e 17, che però valevano
    solo per la regola 15-19 (voce 60).

    Se Google non risponde, `CalendarioNonRaggiungibile` passa al chiamante:
    nel dubbio non si offre nessun orario.
    """
    adesso = ora_utc_naive()
    # La seconda ora di una sessione lunga può finire oltre `a`.
    fine_lettura = a + UN_ORA

    primo_giorno = utc_to_rome(da).date()
    ultimo_giorno = utc_to_rome(a).date()

    # Solo regole da 1 ora, come in genera_slot_da_regola: una regola
    # salvata prima del vincolo sulla durata non produce ore.
    regole = db.query(AvailabilityRule).filter(
        AvailabilityRule.attiva == True,
        AvailabilityRule.durata_slot_ore == 1
    ).all()

    blocchi = db.query(AvailabilityException).filter(
        AvailabilityException.data_fine >= primo_giorno,
        AvailabilityException.data_inizio <= ultimo_giorno
    ).all()

    # Una prenotazione no_show occupa ancora la sua ora: solo la
    # cancellazione la libera. L'orario si legge dallo slot finché le
    # prenotazioni non avranno un orario proprio (pezzo 4.3).
    # Il filtro sull'orario sta nella query perché la tabella cresce sempre;
    # il margine di 2 ore copre le sessioni lunghe iniziate prima di `da`.
    prenotazioni = db.query(Booking).join(Booking.slot).filter(
        Booking.status != "cancelled",
        Slot.start_time < fine_lettura,
        Slot.start_time > da - timedelta(hours=2)
    ).all()
    occupati = [
        (b.slot.start_time, b.slot.start_time + timedelta(hours=b.duration_hours))
        for b in prenotazioni
    ]

    occupati += leggi_eventi_calendario(da, fine_lettura)

    def libera(inizio: datetime) -> bool:
        fine = inizio + UN_ORA
        return inizio > adesso and not any(
            intervalli_si_sovrappongono(inizio, fine, o_inizio, o_fine) for o_inizio, o_fine in occupati
        )

    # Insiemi: due regole sovrapposte nello stesso giorno non producono doppioni.
    da_un_ora, da_due_ore = set(), set()

    giorno = primo_giorno
    while giorno <= ultimo_giorno:
        # Giorni italiani, estremi inclusi, come nel pannello.
        bloccato = any(b.data_inizio <= giorno <= b.data_fine for b in blocchi)
        if not bloccato:
            for regola in regole:
                if regola.giorno_settimana != giorno.weekday():
                    continue
                ore = _ore_della_regola(regola, giorno)
                for inizio in ore:
                    if da <= inizio < a and libera(inizio):
                        da_un_ora.add(inizio)
                for i in range(0, len(ore) - 1, 2):
                    inizio = ore[i]
                    if da <= inizio < a and libera(inizio) and libera(ore[i + 1]):
                        da_due_ore.add(inizio)
        giorno += timedelta(days=1)

    return {1: sorted(da_un_ora), 2: sorted(da_due_ore)}
