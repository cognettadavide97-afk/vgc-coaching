"""Il sito pubblico usa le ore calcolate (pezzo 4.4a, P9).

GET /disponibilita/ elenca le ore in vendita, calcolate da regole, blocchi,
prenotazioni e impegni Google; POST /bookings/ riceve un orario e lo
riverifica con lo stesso calcolo. Le pagine vecchie rimaste nella cache dei
browser prenotano ancora per slot: il server ne ricava l'orario e applica
la stessa verifica (ponte fino al pezzo 4.6).

Le ore diventano prenotabili con apri_ore (conftest.py). L'agenda Google è
vuota e l'orizzonte aperto per tutti i test (conftest.py), salvo dove un
test decide altrimenti.
"""

from datetime import datetime, timedelta

from backend.models.booking import Booking
from backend.models.users import User
from backend.services import disponibilita_service
from backend.services.calendar_service import CalendarioNonRaggiungibile
# Importata qui, prima che la fixture orizzonte_aperto la sostituisca.
from backend.services.disponibilita_service import fine_orizzonte as fine_orizzonte_vera
from conftest import admin_headers, apri_ore, crea_slot, iso
from test_booking import rome_naive_utc

LUNEDI_15 = rome_naive_utc(2030, 1, 7, 15)


def utente_db(db):
    utente = User(nome="Cliente Test", email="cliente@example.com", categoria="senior")
    db.add(utente)
    db.commit()
    db.refresh(utente)
    return utente


def prenota(client, utente, durata=1, **orario):
    return client.post("/bookings/", json={
        "user_id": utente.id, "email": utente.email,
        "duration_hours": durata, "service_type": "vod_review", **orario
    })


def google_irraggiungibile(monkeypatch):
    def guasto(da, a):
        raise CalendarioNonRaggiungibile()
    monkeypatch.setattr(disponibilita_service, "leggi_eventi_calendario", guasto)


# ─── GET /disponibilita/ ──────────────────────────────────────

def test_l_elenco_pubblico_mostra_le_ore_delle_regole_tranne_quelle_vendute(client, db):
    apri_ore(db, LUNEDI_15, ore=4)  # lunedì 15-19
    assert prenota(client, utente_db(db), start_time=iso(LUNEDI_15 + timedelta(hours=1))).status_code == 200

    res = client.get("/disponibilita/")

    assert res.status_code == 200, res.text
    ore = {durata: set(inizi) for durata, inizi in res.json().items()}
    alle = lambda h: iso(LUNEDI_15 + timedelta(hours=h - 15))
    # Le 16 sono vendute: restano 15, 17 e 18.
    assert {alle(15), alle(17), alle(18)} <= ore["1"]
    assert alle(16) not in ore["1"]
    # Sessioni da 2 ore ogni 2 ore dall'inizio della regola: 15 (ma le 16
    # sono prese) e 17.
    assert alle(17) in ore["2"]
    assert alle(15) not in ore["2"]
    # L'orario porta il fuso: senza, il browser lo leggerebbe come ora locale.
    assert alle(15).endswith("+00:00")


def test_l_elenco_pubblico_con_google_irraggiungibile_e_un_503(client, db, monkeypatch):
    # Nel dubbio nessun orario: un'agenda letta come vuota metterebbe in
    # vendita ore che il coach ha già impegnato.
    apri_ore(db, LUNEDI_15)
    google_irraggiungibile(monkeypatch)

    res = client.get("/disponibilita/")

    assert res.status_code == 503


# ─── POST /bookings/ per orario ───────────────────────────────

def test_una_sessione_da_2_ore_alle_18_con_la_regola_18_22(client, db):
    """Voce 60: con gli orari fissi 15 e 17 questa regola non ne avrebbe avuta nessuna."""
    alle_18 = rome_naive_utc(2030, 1, 7, 18)
    apri_ore(db, alle_18, ore=4)

    res = prenota(client, utente_db(db), durata=2, start_time=iso(alle_18))

    assert res.status_code == 200, res.text
    assert db.query(Booking).one().start_time == alle_18


def test_un_ora_che_nessuna_regola_prevede_viene_rifiutata(client, db):
    apri_ore(db, LUNEDI_15)

    res = prenota(client, utente_db(db), start_time=iso(LUNEDI_15 + timedelta(hours=1)))

    assert res.status_code == 400
    assert res.json()["detail"] == "Slot not available"
    assert db.query(Booking).count() == 0


def test_un_ora_oltre_l_orizzonte_viene_rifiutata(client, db, monkeypatch):
    # Con l'orizzonte vero (fine del mese corrente) il 2030 è fuori: il sito
    # non lo offrirebbe, e una richiesta diretta non deve ottenerlo.
    monkeypatch.setattr(disponibilita_service, "fine_orizzonte", fine_orizzonte_vera)
    apri_ore(db, LUNEDI_15)

    res = prenota(client, utente_db(db), start_time=iso(LUNEDI_15))

    assert res.status_code == 400
    assert db.query(Booking).count() == 0


def test_la_prenotazione_con_google_irraggiungibile_e_un_503(client, db, monkeypatch):
    apri_ore(db, LUNEDI_15)
    google_irraggiungibile(monkeypatch)

    res = prenota(client, utente_db(db), start_time=iso(LUNEDI_15))

    assert res.status_code == 503
    assert db.query(Booking).count() == 0


def test_un_orario_senza_fuso_viene_respinto(client, db):
    apri_ore(db, LUNEDI_15)

    res = prenota(client, utente_db(db), start_time=LUNEDI_15.isoformat())

    assert res.status_code == 422


def test_serve_esattamente_uno_fra_orario_e_slot(client, db):
    utente = utente_db(db)
    apri_ore(db, LUNEDI_15)
    slot = crea_slot(db, LUNEDI_15)

    assert prenota(client, utente).status_code == 422
    assert prenota(client, utente, start_time=iso(LUNEDI_15), slot_id=slot.id).status_code == 422


# ─── pagine vecchie: prenotazione per slot ────────────────────

def test_una_pagina_vecchia_prenota_per_slot_e_lo_slot_si_segna_occupato(client, db):
    apri_ore(db, LUNEDI_15)
    slot = crea_slot(db, LUNEDI_15)

    res = prenota(client, utente_db(db), slot_id=slot.id)

    assert res.status_code == 200, res.text
    assert res.json()["slot_id"] == slot.id
    db.refresh(slot)
    # Così la lista della pagina vecchia smette di offrirlo.
    assert slot.is_available is False
    assert db.query(Booking).one().start_time == LUNEDI_15


def test_uno_slot_che_nessuna_regola_prevede_non_si_prenota_piu(client, db):
    # Uno slot creato a mano dal pannello, senza regola: dal 4.4 chi decide è
    # il calcolo (decisione "aperture extra" nel pezzo 4.5).
    slot = crea_slot(db, LUNEDI_15)

    res = prenota(client, utente_db(db), slot_id=slot.id)

    assert res.status_code == 400
    db.refresh(slot)
    assert slot.is_available is True


# ─── orizzonte e regole ───────────────────────────────────────

def test_l_orizzonte_e_la_fine_del_mese_italiano(monkeypatch):
    # Mezzanotte italiana del primo del mese dopo, in UTC: 23:00 d'inverno,
    # 22:00 d'estate.
    casi = [
        (datetime(2026, 12, 15, 10, 0), datetime(2026, 12, 31, 23, 0)),
        (datetime(2026, 7, 10, 10, 0), datetime(2026, 7, 31, 22, 0)),
        # 23:30 UTC del 31 dicembre è già il primo gennaio a Roma: l'orizzonte
        # è la fine di gennaio, non di dicembre.
        (datetime(2026, 12, 31, 23, 30), datetime(2027, 1, 31, 23, 0)),
    ]
    for adesso, atteso in casi:
        monkeypatch.setattr(disponibilita_service, "ora_utc_naive", lambda adesso=adesso: adesso)
        assert fine_orizzonte_vera() == atteso, adesso


def test_una_regola_alle_15_30_viene_rifiutata(client):
    # La guardia sulle ore vendute confronta inizi esatti: una regola a ore
    # piene garantisce che due sessioni sovrapposte abbiano lo stesso inizio.
    res = client.post("/admin/disponibilita/regole", headers=admin_headers(), json={
        "giorno_settimana": 0, "ora_inizio": "15:30", "ora_fine": "19:30", "durata_slot_ore": 1
    })

    assert res.status_code == 422
