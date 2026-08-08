# Questo è probabilmente il file con la logica più "matematica" del
# progetto: genera gli slot concreti a partire da una regola ricorrente
# (es. "ogni martedì 18-22, slot da 1 ora" → 4 slot per ogni martedì delle
# prossime settimane), e applica i blocchi eccezionali (ferie). Vale la
# pena leggerlo con calma perché mischia più concetti insieme: cicli,
# aritmetica sulle date, e conversioni di fuso orario.

from datetime import date, datetime, time, timedelta, timezone
from sqlalchemy.orm import Session
from backend.models.slots import Slot
from backend.models.availability_rule import AvailabilityRule
from backend.models.availability_exception import AvailabilityException
from backend.services.timezone_service import ROME_TZ

# Quante settimane "in avanti" generare gli slot quando si crea una regola.
# È una costante scritta in maiuscolo per convenzione Python: un valore che
# non cambia mai durante l'esecuzione, tenuto in cima al file per essere
# facile da trovare e modificare.
SETTIMANE_GENERAZIONE = 8


def slot_si_sovrappone(db: Session, start_time: datetime, duration_hours: int, escludi_id: int = None) -> bool:
    """
    True se l'intervallo [start_time, start_time + duration_hours) si
    sovrappone a un qualsiasi slot già esistente (indipendentemente dal
    suo stato — libero, prenotato o bloccato). Il claim atomico su un
    singolo slot (P0-5) non basta: due slot DIVERSI che si sovrappongono
    nel tempo potrebbero comunque essere prenotati entrambi, generando
    un doppio impegno reale per il coach.
    """
    # Il modo standard per capire se due intervalli di tempo [A, B) e
    # [C, D) si sovrappongono è controllare "A < D e C < B" (ognuno inizia
    # prima che l'altro finisca). Qui calcoliamo prima "fine" (quando finirebbe
    # il nostro slot candidato) per poter fare questo confronto più sotto.
    fine = start_time + timedelta(hours=duration_hours)

    # Invece di controllare OGNI slot mai creato (che con un database grande
    # sarebbe lento e inutile — uno slot di 3 mesi fa non può mai
    # sovrapporsi a uno di oggi), limitiamo la ricerca a una finestra
    # "generosa" di 6 ore prima dell'inizio: nessuna sessione di coaching
    # dura così tanto, quindi qualsiasi slot che potrebbe sovrapporsi ricade
    # per forza in questo intervallo.
    margine = timedelta(hours=6)

    query = db.query(Slot).filter(
        Slot.start_time < fine,
        Slot.start_time > start_time - margine
    )
    # escludi_id serve per un caso specifico: se stessimo controllando "lo
    # slot X si sovrappone a se stesso?" (es. mentre lo si modifica), non
    # avrebbe senso che risultasse sovrapposto al proprio stesso record.
    # Nel codice attuale questo parametro non viene mai passato, ma la
    # funzione è scritta per essere pronta a quel caso d'uso.
    if escludi_id is not None:
        query = query.filter(Slot.id != escludi_id)

    # Qui il confronto vero e proprio: per ogni slot "candidato" trovato
    # nella finestra di ricerca, controlliamo la condizione di sovrapposizione
    # esatta. Appena ne troviamo uno, restituiamo True e usciamo subito
    # dalla funzione (non serve controllare gli altri).
    for s in query.all():
        s_fine = s.start_time + timedelta(hours=s.duration_hours)
        if start_time < s_fine and s.start_time < fine:
            return True
    return False


def genera_slot_da_regola(regola: AvailabilityRule, db: Session) -> int:
    """
    Genera gli slot concreti corrispondenti a una regola di disponibilità
    ricorrente, per le prossime SETTIMANE_GENERAZIONE settimane. Salta gli
    orari già passati, gli slot già esistenti allo stesso orario (idempotente)
    e le occorrenze che si sovrapporrebbero a uno slot già esistente.
    Restituisce il numero di slot effettivamente creati.
    """
    oggi = date.today()
    ora_utc_adesso = datetime.now(timezone.utc).replace(tzinfo=None)

    # Questa riga calcola "quanti giorni mancano da oggi al prossimo giorno
    # della settimana della regola" (es. se oggi è giovedì e la regola è
    # per martedì, mancano 5 giorni). L'operatore % (modulo, resto della
    # divisione) è il trucco: se il numero venisse negativo (il giorno
    # target è "prima" nella settimana rispetto a oggi), % 7 lo riporta
    # comunque in un intervallo 0-6 corretto, facendo automaticamente il
    # "giro" alla settimana successiva. Prova a fare il conto a mano con
    # oggi=giovedì (weekday=3) e regola=martedì (giorno_settimana=1):
    # (1 - 3) % 7 = -2 % 7 = 5 — corretto, mancano 5 giorni.
    giorni_da_aggiungere = (regola.giorno_settimana - oggi.weekday()) % 7
    prima_data = oggi + timedelta(days=giorni_da_aggiungere)

    creati = 0

    # range(SETTIMANE_GENERAZIONE) produce i numeri 0, 1, 2... fino a 7 (8
    # numeri in tutto): per ognuno, calcoliamo la data di quella settimana
    # aggiungendo "settimana" settimane a prima_data.
    for settimana in range(SETTIMANE_GENERAZIONE):
        giorno = prima_data + timedelta(weeks=settimana)

        # datetime.combine(data, ora) unisce una "data pura" (senza orario)
        # e un "orario puro" (senza data) in un datetime completo — utile
        # perché AvailabilityRule salva giorno e orari separatamente (vedi
        # backend/models/availability_rule.py), ma per fare i calcoli che
        # seguono serve un datetime unico.
        cursore = datetime.combine(giorno, regola.ora_inizio)
        fine_finestra = datetime.combine(giorno, regola.ora_fine)

        # Questo "while" è il cuore della generazione: parte dall'inizio
        # della finestra (es. le 18:00) e avanza di durata_slot_ore in
        # durata_slot_ore (es. ogni ora), creando uno slot per ogni
        # posizione, finché il PROSSIMO slot entrerebbe ancora dentro la
        # finestra (es. si ferma prima di superare le 22:00). È lo stesso
        # tipo di ciclo di un "for i in range(...)", solo che qui il numero
        # di iterazioni non è noto in anticipo — dipende da quanto dura la
        # finestra e quanto dura ogni slot.
        while cursore + timedelta(hours=regola.durata_slot_ore) <= fine_finestra:
            # cursore è ancora "ora italiana senza etichetta di fuso" — lo
            # stesso schema già visto altrove: prima gli attacchiamo
            # esplicitamente ROME_TZ, poi convertiamo davvero in UTC.
            inizio_rome = cursore.replace(tzinfo=ROME_TZ)
            inizio_utc = inizio_rome.astimezone(timezone.utc).replace(tzinfo=None)

            # Creiamo lo slot solo se: è nel futuro (non ha senso generare
            # slot per orari già passati), non esiste già uno slot
            # identico (per non duplicare se la regola venisse rieseguita),
            # e non si sovrapporrebbe a uno slot già esistente (usando la
            # funzione definita sopra in questo stesso file).
            if inizio_utc > ora_utc_adesso:
                esiste_gia = db.query(Slot).filter(Slot.start_time == inizio_utc).first()
                if not esiste_gia and not slot_si_sovrappone(db, inizio_utc, regola.durata_slot_ore):
                    # db.add(...) prepara l'inserimento ma non lo salva
                    # ancora nel database — succede tutto insieme al
                    # db.commit() finale, fuori dal ciclo, per efficienza
                    # (una singola operazione di salvataggio invece di una
                    # per ogni slot).
                    db.add(Slot(start_time=inizio_utc, duration_hours=regola.durata_slot_ore))
                    creati += 1

            cursore += timedelta(hours=regola.durata_slot_ore)

    db.commit()
    return creati


def applica_blocco_eccezionale(eccezione: AvailabilityException, db: Session) -> int:
    """
    Marca come non disponibili (is_available=False, blocked_admin=True) tutti
    gli slot liberi il cui inizio cade nel periodo del blocco eccezionale
    (interpretato come giorni italiani, inclusivi). Non tocca gli slot già
    prenotati o già bloccati per altri motivi.
    Restituisce il numero di slot bloccati.
    """
    # time.min e time.max sono costanti della libreria datetime: rappresentano
    # rispettivamente "00:00:00.000000" e "23:59:59.999999" — l'inizio e la
    # fine assolute di una giornata. Combinandole con le due date del
    # blocco, otteniamo "dall'inizio del primo giorno alla fine dell'ultimo
    # giorno", cioè l'intero periodo, estremi inclusi.
    inizio_rome = datetime.combine(eccezione.data_inizio, time.min).replace(tzinfo=ROME_TZ)
    fine_rome = datetime.combine(eccezione.data_fine, time.max).replace(tzinfo=ROME_TZ)

    inizio_utc = inizio_rome.astimezone(timezone.utc).replace(tzinfo=None)
    fine_utc = fine_rome.astimezone(timezone.utc).replace(tzinfo=None)

    # Prendiamo SOLO gli slot ancora liberi (is_available == True) in
    # questo intervallo: uno slot già prenotato non va toccato da un blocco
    # eccezionale creato dopo — quella prenotazione resta valida, è
    # responsabilità del coach gestirla separatamente.
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
