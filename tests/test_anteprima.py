"""Test dell'anteprima settimanale del pannello (pezzo 4.5a, P9).

`anteprima_settimana` mostra al coach ogni ora della settimana con il suo
stato: in vendita, prenotata, bloccata, passata, oltre l'orizzonte o
occupata su Google. "In vendita" lo decide `calcola_disponibilita`, la
stessa funzione del sito: l'anteprima guarda dalla vetrina dei clienti.

Le date sono fisse e lontane, come in test_disponibilita.py: il 15/07/2030 è
un lunedì, d'estate, quindi le 15:00 italiane sono le 13:00 UTC.
"""

from datetime import date, datetime, time, timedelta

import pytest

from backend.models.availability_exception import AvailabilityException
from backend.models.availability_rule import AvailabilityRule
from backend.models.booking import Booking
from backend.models.users import User
from backend.services import disponibilita_service
from backend.services.calendar_service import CalendarioNonRaggiungibile
from backend.services.disponibilita_service import anteprima_settimana
from backend.services.timezone_service import ora_utc_naive, utc_to_rome
from conftest import admin_headers

LUNEDI = date(2030, 7, 15)
MARTEDI = date(2030, 7, 16)


def utc(ora, giorno=LUNEDI):
    """Ora italiana estiva del giorno indicato, espressa in UTC naive (-2 ore)."""
    return datetime.combine(giorno, time(ora - 2))


@pytest.fixture(autouse=True)
def google(monkeypatch):
    """Agenda Google vuota, salvo che il test ne decida gli impegni."""
    impegni = []
    monkeypatch.setattr(disponibilita_service, "leggi_eventi_calendario", lambda da, a: impegni)
    return impegni


def regola(db, inizio, fine, giorno_settimana=0, attiva=True):
    db.add(AvailabilityRule(giorno_settimana=giorno_settimana, ora_inizio=time(inizio),
                            ora_fine=time(fine), durata_slot_ore=1, attiva=attiva))
    db.commit()


def prenotazione(db, inizio_utc, durata=1, status="confirmed", nome="Mario"):
    """Una prenotazione per orario, senza slot: com'è dal pezzo 4.4."""
    utente = User(nome=nome, email=f"{nome.lower()}@example.com", categoria="senior")
    db.add(utente)
    db.commit()
    db.add(Booking(user_id=utente.id, start_time=inizio_utc, duration_hours=durata,
                   price_cents=2000 * durata, service_type="vod_review", status=status))
    db.commit()


def ore_del_giorno(giorni, giorno):
    """Le ore di un giorno dell'anteprima, come {"15:00": {...}}."""
    voce = next(g for g in giorni if g["data"] == giorno.strftime("%d/%m/%Y"))
    return {o["ora"]: o for o in voce["ore"]}


def test_la_settimana_ha_sette_giorni_da_lunedi(db):
    giorni = anteprima_settimana(db, LUNEDI)

    assert [g["data"] for g in giorni] == [
        (LUNEDI + timedelta(days=i)).strftime("%d/%m/%Y") for i in range(7)
    ]
    assert [g["giorno_settimana"] for g in giorni] == list(range(7))
    assert all(g["ore"] == [] for g in giorni)


def test_le_ore_libere_della_regola_sono_in_vendita(db):
    regola(db, 15, 19)

    ore = ore_del_giorno(anteprima_settimana(db, LUNEDI), LUNEDI)

    assert list(ore) == ["15:00", "16:00", "17:00", "18:00"]
    assert all(o["stato"] == "in_vendita" for o in ore.values())
    # Le sessioni da 2 ore partono ogni 2 ore dall'inizio della regola.
    assert [o["ora"] for o in ore.values() if o["da_due_ore"]] == ["15:00", "17:00"]


def test_una_prenotazione_occupa_le_sue_ore_e_dice_di_chi_e(db):
    regola(db, 15, 19)
    prenotazione(db, utc(15), durata=2)

    ore = ore_del_giorno(anteprima_settimana(db, LUNEDI), LUNEDI)

    assert ore["15:00"]["stato"] == ore["16:00"]["stato"] == "prenotata"
    assert ore["15:00"]["prenotazione"]["cliente"] == "Mario"
    assert ore["15:00"]["prenotazione"]["servizio"] == "vod_review"
    assert ore["17:00"]["stato"] == "in_vendita"


def test_una_prenotazione_cancellata_non_occupa_nulla(db):
    regola(db, 15, 19)
    prenotazione(db, utc(16), status="cancelled")

    ore = ore_del_giorno(anteprima_settimana(db, LUNEDI), LUNEDI)

    assert ore["16:00"]["stato"] == "in_vendita"
    assert ore["16:00"]["prenotazione"] is None


def test_una_prenotazione_fuori_dalle_regole_compare_lo_stesso(db):
    # Per esempio fatta prima che la regola fosse eliminata: la sessione
    # resta in agenda e il coach deve vederla.
    prenotazione(db, utc(10), status="no_show")

    ore = ore_del_giorno(anteprima_settimana(db, LUNEDI), LUNEDI)

    assert list(ore) == ["10:00"]
    assert ore["10:00"]["stato"] == "prenotata"
    assert ore["10:00"]["prenotazione"]["stato"] == "no_show"


def test_un_blocco_chiude_i_suoi_giorni_e_ne_dice_il_motivo(db):
    regola(db, 15, 17)
    regola(db, 15, 17, giorno_settimana=1)
    db.add(AvailabilityException(data_inizio=LUNEDI, data_fine=LUNEDI, motivo="Ferie"))
    db.commit()

    giorni = anteprima_settimana(db, LUNEDI)

    lunedi = ore_del_giorno(giorni, LUNEDI)
    assert {o["stato"] for o in lunedi.values()} == {"bloccata"}
    assert lunedi["15:00"]["motivo"] == "Ferie"
    assert ore_del_giorno(giorni, MARTEDI)["15:00"]["stato"] == "in_vendita"


def test_una_prenotazione_su_un_giorno_bloccato_resta_prenotata(db):
    # Il blocco creato dopo non cancella la sessione: l'anteprima non deve
    # nasconderla dietro "bloccata".
    regola(db, 15, 17)
    prenotazione(db, utc(15))
    db.add(AvailabilityException(data_inizio=LUNEDI, data_fine=LUNEDI, motivo="Ferie"))
    db.commit()

    ore = ore_del_giorno(anteprima_settimana(db, LUNEDI), LUNEDI)

    assert ore["15:00"]["stato"] == "prenotata"
    assert ore["16:00"]["stato"] == "bloccata"


def test_un_impegno_google_e_cio_che_resta(db, google):
    regola(db, 15, 19)
    google.append((utc(16), utc(17)))

    ore = ore_del_giorno(anteprima_settimana(db, LUNEDI), LUNEDI)

    assert ore["16:00"]["stato"] == "google"
    assert [o["ora"] for o in ore.values() if o["stato"] == "in_vendita"] == ["15:00", "17:00", "18:00"]


def test_le_ore_passate_sono_passate(db, monkeypatch):
    regola(db, 15, 19)
    prenotazione(db, utc(15))
    # "Adesso" è lunedì alle 17:30 italiane.
    monkeypatch.setattr(disponibilita_service, "ora_utc_naive", lambda: utc(17) + timedelta(minutes=30))

    ore = ore_del_giorno(anteprima_settimana(db, LUNEDI), LUNEDI)

    # Una sessione già svolta resta una prenotazione, non un'ora passata.
    assert ore["15:00"]["stato"] == "prenotata"
    assert ore["16:00"]["stato"] == ore["17:00"]["stato"] == "passata"
    assert ore["18:00"]["stato"] == "in_vendita"


def test_le_ore_oltre_l_orizzonte_sono_libere_ma_non_in_vendita(db, monkeypatch):
    # Il sito vende fino a 14 giorni da oggi (voce 63). Qui l'orizzonte cade
    # fra lunedì e martedì.
    regola(db, 15, 17)
    regola(db, 15, 17, giorno_settimana=1)
    monkeypatch.setattr(disponibilita_service, "fine_orizzonte", lambda: datetime.combine(MARTEDI, time(0)))

    giorni = anteprima_settimana(db, LUNEDI)

    assert ore_del_giorno(giorni, LUNEDI)["15:00"]["stato"] == "in_vendita"
    martedi = ore_del_giorno(giorni, MARTEDI)
    assert martedi["15:00"]["stato"] == "fuori_orizzonte"
    assert martedi["15:00"]["da_due_ore"] is True


def test_le_regole_non_attive_non_compaiono(db):
    regola(db, 15, 19, attiva=False)

    assert ore_del_giorno(anteprima_settimana(db, LUNEDI), LUNEDI) == {}


def test_con_google_irraggiungibile_l_anteprima_non_risponde(db, monkeypatch):
    regola(db, 15, 19)

    def esplode(da, a):
        raise CalendarioNonRaggiungibile()

    monkeypatch.setattr(disponibilita_service, "leggi_eventi_calendario", esplode)

    with pytest.raises(CalendarioNonRaggiungibile):
        anteprima_settimana(db, LUNEDI)


# ─── endpoint ─────────────────────────────────────────────────

def test_l_endpoint_parte_dal_lunedi_di_questa_settimana(client):
    res = client.get("/admin/disponibilita/anteprima", headers=admin_headers())

    assert res.status_code == 200, res.text
    giorni = res.json()["giorni"]
    assert len(giorni) == 7
    assert giorni[0]["giorno_settimana"] == 0
    # Il giorno italiano, non quello della macchina: in CI è UTC, e la
    # domenica alle 23:30 UTC a Roma è già lunedì.
    oggi = utc_to_rome(ora_utc_naive()).date()
    primo = datetime.strptime(giorni[0]["data"], "%d/%m/%Y").date()
    assert 0 <= (oggi - primo).days <= 6


def test_l_endpoint_vuole_il_login(client):
    res = client.get("/admin/disponibilita/anteprima")

    assert res.status_code in (401, 403)


def test_l_endpoint_rifiuta_settimane_fuori_limite(client):
    for settimana in (-1, 13):
        res = client.get(f"/admin/disponibilita/anteprima?settimana={settimana}", headers=admin_headers())
        assert res.status_code == 422, settimana


def test_l_endpoint_con_google_giu_da_503(client, monkeypatch):
    def esplode(da, a):
        raise CalendarioNonRaggiungibile()

    monkeypatch.setattr(disponibilita_service, "leggi_eventi_calendario", esplode)

    res = client.get("/admin/disponibilita/anteprima", headers=admin_headers())

    assert res.status_code == 503
