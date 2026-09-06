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


# ─── Vincolo sulla durata degli slot ──────────────────────────
#
# Fino al 2026-09-07 `duration_hours` era un intero senza vincoli, e da qui
# passava di tutto. Le conseguenze erano quattro, tutte riprodotte prima di
# correggere:
#
# 1. slot con durata 0 o negativa, accettati senza obiezioni;
# 2. prenotare uno slot con durata fuori listino sollevava `KeyError` sul
#    calcolo del prezzo, cioè un 500 al posto di un errore leggibile;
# 3. uno slot da 2 ore **aggirava il vincolo sugli orari di inizio**: in
#    create_booking quel controllo vive nel ramo che confronta la durata
#    richiesta con quella dello slot, e se coincidono non viene eseguito.
#    È esattamente il rischio che AvailabilityRuleCreate documenta e
#    impedisce per le regole ricorrenti — difeso lì, aperto qui;
# 4. il pannello admin offriva "2 ore", e uno slot così creato non
#    compariva mai ai clienti, perché il form pubblico mostra solo gli slot
#    da 1 ora.

def test_slot_da_due_ore_rifiutato(client):
    """Il caso che aggirava il vincolo sugli orari di inizio."""
    res = client.post(
        "/slots/",
        headers=admin_headers(),
        json={"start_time": (INIZIO + timedelta(days=1)).isoformat(), "duration_hours": 2}
    )

    assert res.status_code == 422


def test_slot_con_durata_zero_o_negativa_rifiutato(client):
    for durata in (0, -1):
        res = client.post(
            "/slots/",
            headers=admin_headers(),
            json={"start_time": (INIZIO + timedelta(days=2)).isoformat(), "duration_hours": durata}
        )
        assert res.status_code == 422, f"durata {durata} avrebbe dovuto essere rifiutata"


def test_slot_da_unora_resta_ammesso(client):
    """La correzione non deve chiudere il caso normale."""
    res = client.post(
        "/slots/",
        headers=admin_headers(),
        json={"start_time": (INIZIO + timedelta(days=3)).isoformat(), "duration_hours": 1}
    )

    assert res.status_code == 200
    assert res.json()["duration_hours"] == 1


def test_prenotazione_con_durata_fuori_listino_rifiutata_senza_errore_del_server(client, db):
    """Prima sollevava KeyError sul calcolo del prezzo: il cliente vedeva un
    500. Ora la richiesta è respinta da Pydantic prima del router."""
    slot = crea_slot(db, INIZIO)
    utente = client.post("/users/", json={"nome": "Tizio", "email": "tizio@example.com"}).json()

    res = client.post("/bookings/", json={
        "user_id": utente["id"], "email": "tizio@example.com",
        "slot_id": slot.id, "duration_hours": 3, "service_type": "vod_review"
    })

    assert res.status_code == 422
