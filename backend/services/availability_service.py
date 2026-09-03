"""Gestione della disponibilità: generazione slot, blocchi, pulizia.

Trasforma le regole ricorrenti in slot concreti, applica i blocchi
eccezionali e rimuove gli slot obsoleti. È il punto in cui le date in ora
italiana delle regole vengono convertite in UTC per il salvataggio.
"""

import calendar
from datetime import date, datetime, time, timedelta, timezone
from sqlalchemy.orm import Session
from backend.models.slots import Slot
from backend.models.booking import Booking
from backend.models.availability_rule import AvailabilityRule
from backend.models.availability_exception import AvailabilityException
from backend.services.timezone_service import ROME_TZ, ora_utc_naive, intervalli_si_sovrappongono


def slot_si_sovrappone(db: Session, start_time: datetime, duration_hours: int, escludi_id: int = None) -> bool:
    """Indica se l'intervallo indicato si sovrappone a uno slot esistente.

    Considera gli slot in qualsiasi stato. Il claim atomico applicato in
    fase di prenotazione protegge un singolo slot dalla doppia
    prenotazione, ma non impedisce che due slot *distinti* si accavallino
    nel tempo, producendo un doppio impegno reale per il coach.

    `escludi_id` esclude uno slot dal confronto, per poterlo verificare
    contro tutti gli altri senza che risulti sovrapposto a sé stesso.
    Nessun chiamante attuale lo usa.
    """
    fine = start_time + timedelta(hours=duration_hours)

    # Finestra di ricerca limitata invece di scorrere l'intera tabella:
    # nessuna sessione dura più di 6 ore, quindi uno slot che inizia prima
    # di questo margine non può sovrapporsi.
    margine = timedelta(hours=6)

    query = db.query(Slot).filter(
        Slot.start_time < fine,
        Slot.start_time > start_time - margine
    )
    if escludi_id is not None:
        query = query.filter(Slot.id != escludi_id)

    for s in query.all():
        s_fine = s.start_time + timedelta(hours=s.duration_hours)
        if intervalli_si_sovrappongono(start_time, fine, s.start_time, s_fine):
            return True
    return False


def genera_slot_da_regola(regola: AvailabilityRule, db: Session) -> int:
    """Crea gli slot previsti da una regola, fino alla fine del mese corrente.

    Restituisce il numero di slot creati. È idempotente: salta gli orari
    già passati, gli slot già esistenti allo stesso orario e quelli che si
    sovrapporrebbero a slot esistenti, quindi può essere rieseguita senza
    produrre duplicati. Il job notturno la richiama ogni giorno: la
    finestra "fine mese" si allarga da sola all'inizio di ogni mese.

    Genera esclusivamente slot da 1 ora. Uno slot da 2 ore aggirerebbe il
    vincolo sugli orari di inizio ammessi per le sessioni lunghe, che si
    applica solo all'unione di due slot da 1 ora. Lo schema di creazione
    delle regole rifiuta già durate diverse; questo controllo è la seconda
    barriera, e neutralizza eventuali regole salvate prima che il vincolo
    esistesse — smettono di generare invece di continuare a produrre slot
    non conformi.
    """
    if regola.durata_slot_ore != 1:
        return 0

    oggi = date.today()
    ora_utc_adesso = ora_utc_naive()

    ultimo_giorno_mese = date(oggi.year, oggi.month, calendar.monthrange(oggi.year, oggi.month)[1])

    # Distanza in giorni dalla prossima occorrenza del giorno della regola.
    # Il modulo gestisce il passaggio alla settimana successiva quando il
    # giorno target precede oggi.
    giorni_da_aggiungere = (regola.giorno_settimana - oggi.weekday()) % 7
    prima_data = oggi + timedelta(days=giorni_da_aggiungere)

    creati = 0

    settimana = 0
    while True:
        giorno = prima_data + timedelta(weeks=settimana)
        if giorno > ultimo_giorno_mese:
            break
        settimana += 1

        cursore = datetime.combine(giorno, regola.ora_inizio)
        fine_finestra = datetime.combine(giorno, regola.ora_fine)

        # Avanza a passi di durata_slot_ore e si ferma quando lo slot
        # successivo uscirebbe dalla finestra oraria della regola.
        while cursore + timedelta(hours=regola.durata_slot_ore) <= fine_finestra:
            # Gli orari della regola sono ora italiana: qui vengono
            # etichettati e convertiti in UTC per il salvataggio.
            inizio_rome = cursore.replace(tzinfo=ROME_TZ)
            inizio_utc = inizio_rome.astimezone(timezone.utc).replace(tzinfo=None)

            if inizio_utc > ora_utc_adesso:
                esiste_gia = db.query(Slot).filter(Slot.start_time == inizio_utc).first()
                if not esiste_gia and not slot_si_sovrappone(db, inizio_utc, regola.durata_slot_ore):
                    db.add(Slot(start_time=inizio_utc, duration_hours=regola.durata_slot_ore))
                    creati += 1

            cursore += timedelta(hours=regola.durata_slot_ore)

    # Commit unico fuori dai cicli: un salvataggio per chiamata, non per slot.
    db.commit()
    return creati


def elimina_slot_obsoleti(db: Session) -> int:
    """Elimina gli slot passati che non sono mai stati prenotati.

    Riguarda sia gli slot rimasti liberi sia quelli bloccati: senza
    prenotazioni collegate non hanno valore storico. Senza questa pulizia
    si accumulano indefinitamente e riempiono le prime pagine della lista
    slot del pannello, ordinata per data crescente.

    Uno slot con una prenotazione collegata non viene mai toccato, neppure
    se la prenotazione è stata cancellata (la riga resta con
    status="cancelled") o se lo slot è il secondario di una sessione da 2
    ore. È lo stesso criterio della cancellazione manuale.
    """
    ora_utc = ora_utc_naive()

    slot_prenotati_id = set(
        row[0] for row in db.query(Booking.slot_id).all()
    ) | set(
        row[0] for row in db.query(Booking.slot_id_secondario).filter(Booking.slot_id_secondario.isnot(None)).all()
    )

    candidati = db.query(Slot).filter(Slot.start_time < ora_utc).all()

    eliminati = 0
    for slot in candidati:
        if slot.id in slot_prenotati_id:
            continue
        db.delete(slot)
        eliminati += 1

    db.commit()
    return eliminati


def applica_blocco_eccezionale(eccezione: AvailabilityException, db: Session) -> int:
    """Blocca gli slot liberi che ricadono nel periodo indicato.

    Restituisce il numero di slot bloccati. Il periodo è inteso in giorni
    italiani, estremi inclusi.
    """
    # time.min/time.max estendono le due date all'intera giornata, così il
    # blocco copre dal primo istante del primo giorno all'ultimo dell'ultimo.
    inizio_rome = datetime.combine(eccezione.data_inizio, time.min).replace(tzinfo=ROME_TZ)
    fine_rome = datetime.combine(eccezione.data_fine, time.max).replace(tzinfo=ROME_TZ)

    inizio_utc = inizio_rome.astimezone(timezone.utc).replace(tzinfo=None)
    fine_utc = fine_rome.astimezone(timezone.utc).replace(tzinfo=None)

    # Solo gli slot ancora liberi: una prenotazione già confermata resta
    # valida anche se il coach aggiunge un blocco successivo, e va gestita
    # separatamente.
    slot_liberi = db.query(Slot).filter(
        Slot.is_available == True,
        Slot.start_time >= inizio_utc,
        Slot.start_time <= fine_utc
    ).all()

    for slot in slot_liberi:
        slot.is_available = False
        slot.blocked_admin = True

    db.commit()
    return len(slot_liberi)
