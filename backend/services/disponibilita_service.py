"""Disponibilità calcolata: le ore prenotabili ricavate al momento (decisione P9).

Sostituirà la tabella `slots`, che è una copia della disponibilità scritta
in anticipo: ogni cambiamento della realtà (un impegno spostato su Google,
un blocco eliminato) andava ricopiato a mano o da un job, e finché non
succedeva la copia mentiva. Qui non si salva nulla: si parte dalle regole
ricorrenti e si tolgono blocchi, prenotazioni e impegni Google, ogni volta
che qualcuno chiede. Una sola fonte di verità, niente da tenere allineato.

Dal pezzo 4.4 è la fonte delle ore che il sito pubblico mostra
(`disponibilita_pubblica`) e la verifica di ogni prenotazione
(`ora_prenotabile`). L'orario delle prenotazioni si legge dalla prenotazione
stessa (pezzo 4.3). Dal 4.5 ne legge anche il pannello: la dashboard e
l'anteprima settimanale (`anteprima_settimana`).
"""

from datetime import date, datetime, time, timedelta, timezone
from sqlalchemy.orm import Session
from backend.models.availability_exception import AvailabilityException
from backend.models.availability_rule import AvailabilityRule
from backend.models.booking import Booking
from backend.services.calendar_service import leggi_eventi_calendario
from backend.services.timezone_service import (
    ROME_TZ, formatta_data_ora_rome, ora_utc_naive, utc_to_rome, intervalli_si_sovrappongono
)

UN_ORA = timedelta(hours=1)

# Con quanti giorni di anticipo si può prenotare, oltre a oggi (voce 63).
# Più è grande, prima vanno inseriti i blocchi: un giorno entra in vendita
# GIORNI_PRENOTABILI giorni prima, e le ferie devono esserci già.
GIORNI_PRENOTABILI = 14


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


def _regole_valide(db: Session) -> list[AvailabilityRule]:
    """Le regole che producono ore: attive e da 1 ora.

    Solo regole da 1 ora: una regola salvata prima del vincolo sulla durata
    (AvailabilityRuleCreate) non produce ore, invece di produrne di
    sbagliate. Una funzione sola perché calcolo e anteprima devono vedere le
    stesse regole.
    """
    return db.query(AvailabilityRule).filter(
        AvailabilityRule.attiva == True,
        AvailabilityRule.durata_slot_ore == 1
    ).all()


def _blocchi_fra(db: Session, primo_giorno: date, ultimo_giorno: date) -> list[AvailabilityException]:
    """I blocchi che toccano almeno un giorno italiano fra i due, estremi inclusi."""
    return db.query(AvailabilityException).filter(
        AvailabilityException.data_fine >= primo_giorno,
        AvailabilityException.data_inizio <= ultimo_giorno
    ).all()


def _prenotazioni_fra(db: Session, da: datetime, a: datetime) -> list[Booking]:
    """Le prenotazioni non cancellate che possono toccare l'intervallo [da, a).

    Una prenotazione no_show occupa ancora la sua ora: solo la
    cancellazione la libera.
    Il filtro sull'orario sta nella query perché la tabella cresce sempre;
    il margine di 2 ore copre le sessioni lunghe iniziate prima di `da`.
    """
    return db.query(Booking).filter(
        Booking.status != "cancelled",
        Booking.start_time < a,
        Booking.start_time > da - timedelta(hours=2)
    ).all()


def fine_orizzonte() -> datetime:
    """Fin dove si può prenotare: la mezzanotte italiana dopo il giorno oggi + GIORNI_PRENOTABILI, in UTC naive.

    Una finestra scorrevole (voce 63, decisa il 2026-11-21): il cliente può
    prenotare sempre lo stesso anticipo, e ogni notte si apre un giorno in
    fondo. Fino ad allora l'orizzonte era la fine del mese corrente, eredità
    degli slot generati fino a fine mese (intervento 38): circa trenta giorni
    a inizio mese e quasi nessuno negli ultimi, così chi a fine mese cercava
    un'ora per la settimana dopo non trovava nulla.

    Il confine cade a mezzanotte, non a quest'ora fra 14 giorni: il cliente
    vede giornate intere, mai una giornata tagliata a metà. Il giorno si
    conta sull'orologio di Roma e solo dopo si converte in UTC, così il
    cambio dell'ora legale sposta l'orario UTC e non il confine italiano.
    """
    oggi = utc_to_rome(ora_utc_naive()).date()
    primo_giorno_escluso = oggi + timedelta(days=GIORNI_PRENOTABILI + 1)
    return datetime.combine(primo_giorno_escluso, time.min, tzinfo=ROME_TZ).astimezone(timezone.utc).replace(tzinfo=None)


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

    regole = _regole_valide(db)
    blocchi = _blocchi_fra(db, primo_giorno, ultimo_giorno)
    prenotazioni = _prenotazioni_fra(db, da, fine_lettura)
    occupati = [
        (b.start_time, b.start_time + timedelta(hours=b.duration_hours))
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


def disponibilita_pubblica(db: Session) -> dict[int, list[datetime]]:
    """Le ore che il sito pubblico offre: da adesso alla fine dell'orizzonte."""
    return calcola_disponibilita(db, ora_utc_naive(), fine_orizzonte())


def ora_prenotabile(db: Session, inizio: datetime, durata: int) -> bool:
    """Indica se una sessione di `durata` ore può iniziare a `inizio` (UTC naive).

    È la stessa domanda dell'elenco pubblico, fatta su un solo orario: chi
    prenota con una richiesta diretta, scavalcando il sito, non ottiene
    nulla che il sito non offrirebbe. Il calcolo su una finestra di un
    minuto legge da Google soltanto le ore attorno a quella richiesta.

    Non è la protezione contro due richieste simultanee sulla stessa ora:
    quella è la tabella ore_prenotate (models/ora_prenotata.py). Qui si
    risponde a "è in vendita?", là a "è già venduta?".
    """
    if inizio >= fine_orizzonte():
        return False
    libere = calcola_disponibilita(db, inizio, inizio + timedelta(minutes=1))
    return inizio in libere.get(durata, [])


def anteprima_settimana(db: Session, lunedi: date) -> list[dict]:
    """Ogni ora della settimana italiana da `lunedi`, con il suo stato, per il pannello.

    Restituisce sette giorni, ognuno con le sue ore in ordine. Le ore sono
    quelle delle regole valide più quelle di ogni prenotazione non
    cancellata della settimana, anche fuori dalle regole (fatta prima che
    la regola fosse eliminata): la sessione resta in agenda e il coach deve
    vederla. Lo stato di ciascuna, nell'ordine in cui si controlla:

    - "prenotata": vince su tutto. Un blocco creato dopo non cancella la
      sessione, e una sessione già svolta resta una prenotazione;
    - "passata";
    - "bloccata": il giorno cade in un blocco, di cui si riporta il motivo;
    - "in_vendita" o "fuori_orizzonte": libera secondo calcola_disponibilita,
      la stessa funzione del sito, prima o dopo la fine dell'orizzonte;
    - "google": ciò che resta. Esclusi gli altri motivi, l'unico per cui il
      calcolo può scartare un'ora della regola è un impegno su Google
      Calendar. Dedurlo per esclusione evita una seconda lettura di Google;
      se il calcolo avesse un giorno un motivo nuovo, va aggiunto qui prima
      di questo ramo, o l'anteprima lo chiamerebbe "google".

    Valori grezzi, come in analytics: etichette e colori sono del frontend.
    Se Google non risponde, `CalendarioNonRaggiungibile` passa al chiamante.
    """
    giorni = [lunedi + timedelta(days=i) for i in range(7)]

    def mezzanotte_utc(giorno: date) -> datetime:
        return datetime.combine(giorno, time.min, tzinfo=ROME_TZ).astimezone(timezone.utc).replace(tzinfo=None)

    da, a = mezzanotte_utc(giorni[0]), mezzanotte_utc(giorni[-1] + timedelta(days=1))

    # L'unica lettura di Google: il resto si deduce (vedi "google" sopra).
    libere = calcola_disponibilita(db, da, a)
    in_vendita, da_due_ore = set(libere[1]), set(libere[2])
    adesso = ora_utc_naive()
    orizzonte = fine_orizzonte()

    regole = _regole_valide(db)
    blocchi = _blocchi_fra(db, giorni[0], giorni[-1])
    prenotazioni = _prenotazioni_fra(db, da, a)

    # Insiemi per giorno italiano: regole sovrapposte, o una prenotazione
    # dentro la regola, non producono la stessa ora due volte.
    ore_per_giorno = {giorno: set() for giorno in giorni}
    for giorno in giorni:
        for regola in regole:
            if regola.giorno_settimana == giorno.weekday():
                ore_per_giorno[giorno].update(_ore_della_regola(regola, giorno))
    for p in prenotazioni:
        for i in range(p.duration_hours):
            inizio = p.start_time + i * UN_ORA
            giorno = utc_to_rome(inizio).date()
            if giorno in ore_per_giorno:
                ore_per_giorno[giorno].add(inizio)

    def stato_ora(inizio: datetime, giorno: date) -> dict:
        voce = {"ora": formatta_data_ora_rome(inizio)[1], "stato": None, "da_due_ore": False,
                "prenotazione": None, "motivo": None}
        prenotazione = next((
            p for p in prenotazioni
            if intervalli_si_sovrappongono(inizio, inizio + UN_ORA,
                                           p.start_time, p.start_time + timedelta(hours=p.duration_hours))
        ), None)
        blocco = next((b for b in blocchi if b.data_inizio <= giorno <= b.data_fine), None)

        if prenotazione is not None:
            voce["stato"] = "prenotata"
            voce["prenotazione"] = {"id": prenotazione.id, "cliente": prenotazione.user.nome,
                                    "servizio": prenotazione.service_type, "stato": prenotazione.status}
        elif inizio <= adesso:
            voce["stato"] = "passata"
        elif blocco is not None:
            voce["stato"] = "bloccata"
            voce["motivo"] = blocco.motivo
        elif inizio in in_vendita:
            # Stesso confine di ora_prenotabile: dall'orizzonte in poi non si vende.
            voce["stato"] = "in_vendita" if inizio < orizzonte else "fuori_orizzonte"
            voce["da_due_ore"] = inizio in da_due_ore
        else:
            voce["stato"] = "google"
        return voce

    return [
        {
            "data": giorno.strftime("%d/%m/%Y"),
            "giorno_settimana": giorno.weekday(),
            "ore": [stato_ora(inizio, giorno) for inizio in sorted(ore_per_giorno[giorno])]
        }
        for giorno in giorni
    ]
