"""Test della disponibilità calcolata (decisione P9, pezzo 4.2).

`calcola_disponibilita` ricava le ore prenotabili da regole, blocchi,
prenotazioni e impegni Google, senza salvare nulla. Google non viene mai
contattato: la lettura degli impegni è sostituita da una funzione che
restituisce gli intervalli decisi dal test. La conversione degli eventi
Google in intervalli ha i suoi test in test_percorsi_critici_trasformazione.py.

Le date sono fisse e lontane nel futuro, così "adesso" non le tocca: il
16/07/2030 è un martedì, d'estate, quindi le 15:00 italiane sono le 13:00 UTC.
"""

from datetime import date, datetime, time, timedelta

import pytest

from backend.models.availability_exception import AvailabilityException
from backend.models.availability_rule import AvailabilityRule
from backend.models.booking import Booking
from backend.models.users import User
from backend.services import disponibilita_service
from backend.services.calendar_service import CalendarioNonRaggiungibile
from backend.services.disponibilita_service import calcola_disponibilita
from backend.services.timezone_service import ora_utc_naive
from conftest import crea_slot

MARTEDI = date(2030, 7, 16)
INIZIO_GIORNO = datetime(2030, 7, 16, 0, 0)
FINE_GIORNO = datetime(2030, 7, 17, 0, 0)


def utc(ora, giorno=MARTEDI):
    """Ora italiana estiva del giorno indicato, espressa in UTC naive (-2 ore)."""
    return datetime.combine(giorno, time(ora - 2))


@pytest.fixture(autouse=True)
def google(monkeypatch):
    """Agenda Google vuota, salvo che il test ne decida gli impegni."""
    impegni = []
    monkeypatch.setattr(disponibilita_service, "leggi_eventi_calendario", lambda da, a: impegni)
    return impegni


def regola(db, inizio, fine, giorno_settimana=1, attiva=True):
    db.add(AvailabilityRule(giorno_settimana=giorno_settimana, ora_inizio=time(inizio),
                            ora_fine=time(fine), durata_slot_ore=1, attiva=attiva))
    db.commit()


def prenotazione(db, inizio_utc, durata=1, status="confirmed"):
    utente = db.query(User).first()
    if utente is None:
        utente = User(nome="Cliente", email="c@example.com", categoria="senior")
        db.add(utente)
        db.commit()
    slot = crea_slot(db, inizio_utc, is_available=False)
    db.add(Booking(user_id=utente.id, slot_id=slot.id, duration_hours=durata,
                   price_cents=2000 * durata, service_type="vod_review", status=status))
    db.commit()


def test_una_regola_15_19_offre_quattro_ore_e_due_sessioni_lunghe(db):
    regola(db, 15, 19)

    libere = calcola_disponibilita(db, INIZIO_GIORNO, FINE_GIORNO)

    assert libere[1] == [utc(15), utc(16), utc(17), utc(18)]
    # Le sessioni da 2 ore partono ogni 2 ore dall'inizio della regola: 15-17
    # e 17-19, mai 16-18, che lascerebbe isolate le 15 e le 18.
    assert libere[2] == [utc(15), utc(17)]


def test_una_regola_18_22_ha_sessioni_lunghe_alle_18_e_alle_20(db):
    """Voce 60: con gli orari fissi 15 e 17 questa regola non ne avrebbe nessuna."""
    regola(db, 18, 22)

    libere = calcola_disponibilita(db, INIZIO_GIORNO, FINE_GIORNO)

    assert libere[2] == [utc(18), utc(20)]


def test_un_ora_dispari_in_fondo_alla_regola_resta_solo_da_un_ora(db):
    regola(db, 15, 20)

    libere = calcola_disponibilita(db, INIZIO_GIORNO, FINE_GIORNO)

    assert libere[1][-1] == utc(19)
    assert libere[2] == [utc(15), utc(17)]


def test_una_prenotazione_confermata_toglie_la_sua_ora_e_la_sessione_lunga(db):
    regola(db, 15, 19)
    prenotazione(db, utc(16))

    libere = calcola_disponibilita(db, INIZIO_GIORNO, FINE_GIORNO)

    assert libere[1] == [utc(15), utc(17), utc(18)]
    # Le 15 restano libere, ma la sessione 15-17 no: la seconda ora è presa.
    assert libere[2] == [utc(17)]


def test_una_prenotazione_cancellata_non_occupa_nulla(db):
    regola(db, 15, 19)
    prenotazione(db, utc(16), status="cancelled")

    libere = calcola_disponibilita(db, INIZIO_GIORNO, FINE_GIORNO)

    assert utc(16) in libere[1]
    assert libere[2] == [utc(15), utc(17)]


def test_una_prenotazione_da_due_ore_toglie_entrambe_le_ore(db):
    regola(db, 15, 19)
    prenotazione(db, utc(15), durata=2)

    libere = calcola_disponibilita(db, INIZIO_GIORNO, FINE_GIORNO)

    assert libere[1] == [utc(17), utc(18)]


def test_un_blocco_toglie_i_suoi_giorni_estremi_inclusi(db):
    regola(db, 15, 19)
    db.add(AvailabilityException(data_inizio=date(2030, 7, 10), data_fine=MARTEDI))
    db.commit()

    libere = calcola_disponibilita(db, INIZIO_GIORNO, FINE_GIORNO)

    assert libere == {1: [], 2: []}


def test_un_impegno_google_toglie_le_ore_che_tocca(db, google):
    regola(db, 15, 19)
    # 16:30-17:30 italiane: tocca sia le 16 sia le 17.
    google.append((utc(16) + timedelta(minutes=30), utc(17) + timedelta(minutes=30)))

    libere = calcola_disponibilita(db, INIZIO_GIORNO, FINE_GIORNO)

    assert libere[1] == [utc(15), utc(18)]
    assert libere[2] == []


def test_un_impegno_che_finisce_quando_l_ora_inizia_non_la_toglie(db, google):
    """Intervalli semiaperti: 14-15 e 15-16 si toccano, non si sovrappongono."""
    regola(db, 15, 19)
    google.append((utc(14), utc(15)))

    libere = calcola_disponibilita(db, INIZIO_GIORNO, FINE_GIORNO)

    assert libere[1][0] == utc(15)


def test_con_google_irraggiungibile_non_esce_nessun_orario(db, monkeypatch):
    """Nel dubbio si chiude: un guasto non deve sembrare un'agenda vuota (4.1)."""
    regola(db, 15, 19)

    def esplode(da, a):
        raise CalendarioNonRaggiungibile()

    monkeypatch.setattr(disponibilita_service, "leggi_eventi_calendario", esplode)

    with pytest.raises(CalendarioNonRaggiungibile):
        calcola_disponibilita(db, INIZIO_GIORNO, FINE_GIORNO)


def test_le_regole_non_attive_non_producono_ore(db):
    regola(db, 15, 19, attiva=False)

    assert calcola_disponibilita(db, INIZIO_GIORNO, FINE_GIORNO) == {1: [], 2: []}


def test_le_ore_gia_passate_non_si_offrono(db):
    adesso = ora_utc_naive()
    # Una regola su tutti i giorni della settimana, per tutta la giornata:
    # oggi ha di sicuro ore passate e, prima delle 23, ore future.
    for giorno in range(7):
        regola(db, 0, 23, giorno_settimana=giorno)

    libere = calcola_disponibilita(db, adesso - timedelta(days=1), adesso + timedelta(days=1))

    assert libere[1]
    assert all(inizio > adesso for inizio in libere[1] + libere[2])


def test_due_regole_sovrapposte_non_producono_doppioni(db):
    regola(db, 15, 19)
    regola(db, 17, 21)

    libere = calcola_disponibilita(db, INIZIO_GIORNO, FINE_GIORNO)

    assert libere[1] == [utc(ora) for ora in range(15, 21)]
    assert libere[2] == [utc(15), utc(17), utc(19)]


def test_l_ora_legale_sposta_l_orario_utc(db):
    """La regola delle 15 è alle 14:00 UTC d'inverno e alle 13:00 UTC d'estate.

    L'ora legale 2027 inizia domenica 28 marzo: la domenica prima vale
    ancora l'ora solare.
    """
    regola(db, 15, 16, giorno_settimana=6)

    libere = calcola_disponibilita(db, datetime(2027, 3, 20), datetime(2027, 3, 29))

    assert libere[1] == [datetime(2027, 3, 21, 14), datetime(2027, 3, 28, 13)]


def test_il_calcolo_non_salva_nulla(db):
    """Chiamarlo non cambia il database: niente slot generati."""
    from backend.models.slots import Slot
    regola(db, 15, 19)

    calcola_disponibilita(db, INIZIO_GIORNO, FINE_GIORNO)

    assert db.query(Slot).count() == 0
