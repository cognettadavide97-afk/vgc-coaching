# Copre backend/routers/slots.py — finora senza nessun test dedicato,
# nonostante sia l'endpoint pubblico che il form di prenotazione chiama per
# primo (GET /slots/) e quello che il pannello admin usa per creare
# disponibilità manuale (POST /slots/). Vedi tests/conftest.py per come
# sono preparati client/db.

from datetime import datetime, timedelta

from backend.models.slots import Slot
from conftest import admin_headers, crea_slot

INIZIO = datetime(2030, 1, 7, 15, 0, 0)


def test_get_slots_mostra_solo_slot_futuri_e_disponibili(client, db):
    futuro_libero = crea_slot(db, INIZIO, is_available=True)
    crea_slot(db, INIZIO + timedelta(hours=1), is_available=False)  # occupato: non deve comparire
    crea_slot(db, datetime(2020, 1, 7, 15, 0, 0), is_available=True)  # passato: non deve comparire

    res = client.get("/slots/")

    assert res.status_code == 200
    ids = [s["id"] for s in res.json()]
    assert ids == [futuro_libero.id]


# Qui c'era test_get_slot_singolo, che copriva GET /slots/{slot_id}. È stato
# rimosso insieme all'endpoint (vedi REVISIONE_2026-09-01.md, ritrovamento
# R12): non un test aggiustato per farlo passare, ma un test di una
# funzionalità deliberatamente eliminata.


def test_create_slot_richiede_admin(client, db):
    res = client.post("/slots/", json={
        "start_time": INIZIO.isoformat(),
        "duration_hours": 1
    })
    assert res.status_code == 401


def test_create_slot_come_admin(client, db):
    res = client.post(
        "/slots/",
        headers=admin_headers(),
        json={"start_time": INIZIO.isoformat(), "duration_hours": 1}
    )
    assert res.status_code == 200, res.text
    assert res.json()["duration_hours"] == 1

    assert db.query(Slot).count() == 1


def test_create_slot_sovrapposto_viene_rifiutato(client, db):
    crea_slot(db, INIZIO, duration_hours=2)

    # Uno slot da 1 ora che inizia a metà di quello già esistente (2 ore) —
    # si sovrappone, va rifiutato anche se non è lo STESSO orario esatto.
    res = client.post(
        "/slots/",
        headers=admin_headers(),
        json={"start_time": (INIZIO + timedelta(minutes=30)).isoformat(), "duration_hours": 1}
    )

    assert res.status_code == 400
