# Copre il cuore del progetto: create_booking in backend/routers/booking.py
# (vedi i commenti lì per il "perché" della logica) e la cancellazione
# self-service. Vedi tests/conftest.py per come sono preparati client/db e
# perché le integrazioni esterne sono finte in tutti questi test.

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from backend.models.slots import Slot
from backend.models.package import Package
from backend.services.auth_service import crea_token_studente

ROME_TZ = ZoneInfo("Europe/Rome")


def rome_naive_utc(anno, mese, giorno, ora):
    """Costruisce un datetime naive-UTC (come salvato nel DB, vedi backend/models/slots.py)
    a partire da un orario espresso in ora ITALIANA — serve per testare
    ORE_INIZIO_VALIDE_2H in backend/routers/booking.py, che ragiona in ora
    italiana, senza dover calcolare a mano l'offset UTC+1/+2 di ogni data."""
    return datetime(anno, mese, giorno, ora, tzinfo=ROME_TZ).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def crea_slot(db, start_time, duration_hours=1, is_available=True):
    slot = Slot(start_time=start_time, duration_hours=duration_hours, is_available=is_available)
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return slot


def crea_utente(client, email="cliente@example.com"):
    res = client.post("/users/", json={
        "nome": "Cliente Test",
        "email": email,
        "categoria": "senior",
        "discord_tag": "clientetest",
        "telefono": None
    })
    assert res.status_code == 200, res.text
    return res.json()


# Punto di partenza fisso per tutti gli orari di test: un lunedì alle 15:00
# ora italiana, ben nel futuro — non importa la data esatta, solo che sia
# sempre dopo "adesso" (i controlli di create_booking/cancella si basano su
# datetime.now()), che le ore successive siano libere per i test sul merge
# di due slot da 1h, E che sia un orario di inizio valido per una
# prenotazione da 2 ore (vedi ORE_INIZIO_VALIDE_2H in
# backend/routers/booking.py e i test dedicati più sotto).
INIZIO = rome_naive_utc(2030, 1, 7, 15)


def test_prenotazione_1_ora(client, db):
    utente = crea_utente(client)
    slot = crea_slot(db, INIZIO)

    res = client.post("/bookings/", json={
        "user_id": utente["id"],
        "slot_id": slot.id,
        "duration_hours": 1,
        "service_type": "vod_review"
    })

    assert res.status_code == 200, res.text
    prenotazione = res.json()
    assert prenotazione["slot_id"] == slot.id
    assert prenotazione["slot_id_secondario"] is None
    assert prenotazione["price_cents"] == 2000  # 20€/ora, vedi TABELLA_PREZZI in booking.py
    assert prenotazione["status"] == "confirmed"


def test_prenotazione_2_ore_unisce_due_slot_adiacenti(client, db):
    utente = crea_utente(client)
    primo = crea_slot(db, INIZIO)
    secondo = crea_slot(db, INIZIO + timedelta(hours=1))

    res = client.post("/bookings/", json={
        "user_id": utente["id"],
        "slot_id": primo.id,
        "duration_hours": 2,
        "service_type": "vod_review"
    })

    assert res.status_code == 200, res.text
    prenotazione = res.json()
    assert prenotazione["slot_id"] == primo.id
    assert prenotazione["slot_id_secondario"] == secondo.id
    assert prenotazione["price_cents"] == 4000

    # Entrambi gli slot devono risultare occupati, non solo il primo.
    db.refresh(primo)
    db.refresh(secondo)
    assert primo.is_available is False
    assert secondo.is_available is False


def test_prenotazione_2_ore_alle_17_e_permessa(client, db):
    utente = crea_utente(client)
    primo = crea_slot(db, rome_naive_utc(2030, 1, 7, 17))
    crea_slot(db, rome_naive_utc(2030, 1, 7, 18))

    res = client.post("/bookings/", json={
        "user_id": utente["id"],
        "slot_id": primo.id,
        "duration_hours": 2,
        "service_type": "vod_review"
    })

    assert res.status_code == 200, res.text


def test_prenotazione_2_ore_alle_16_e_rifiutata(client, db):
    # Regola di prodotto: una sessione da 2 ore può iniziare SOLO alle 15:00
    # o alle 17:00 (vedi ORE_INIZIO_VALIDE_2H in backend/routers/booking.py)
    # — anche se sia lo slot delle 16 sia quello delle 17 esistono e sono
    # entrambi liberi, il backend deve comunque rifiutare la richiesta.
    utente = crea_utente(client)
    primo = crea_slot(db, rome_naive_utc(2030, 1, 7, 16))
    secondo = crea_slot(db, rome_naive_utc(2030, 1, 7, 17))

    res = client.post("/bookings/", json={
        "user_id": utente["id"],
        "slot_id": primo.id,
        "duration_hours": 2,
        "service_type": "vod_review"
    })

    assert res.status_code == 400
    db.refresh(primo)
    db.refresh(secondo)
    assert primo.is_available is True
    assert secondo.is_available is True


def test_prenotazione_2_ore_fallisce_se_ora_successiva_assente(client, db):
    utente = crea_utente(client)
    # Solo UNO slot da 1h disponibile: non esiste l'ora successiva.
    primo = crea_slot(db, INIZIO)

    res = client.post("/bookings/", json={
        "user_id": utente["id"],
        "slot_id": primo.id,
        "duration_hours": 2,
        "service_type": "vod_review"
    })

    assert res.status_code == 400
    # Lo slot originale non deve essere stato toccato da un tentativo fallito.
    db.refresh(primo)
    assert primo.is_available is True


def test_prenotazione_2_ore_fallisce_se_ora_successiva_gia_occupata(client, db):
    utente = crea_utente(client)
    primo = crea_slot(db, INIZIO)
    crea_slot(db, INIZIO + timedelta(hours=1), is_available=False)  # già preso da qualcun altro

    res = client.post("/bookings/", json={
        "user_id": utente["id"],
        "slot_id": primo.id,
        "duration_hours": 2,
        "service_type": "vod_review"
    })

    assert res.status_code == 400
    db.refresh(primo)
    assert primo.is_available is True


def test_slot_gia_occupato_viene_rifiutato(client, db):
    utente = crea_utente(client)
    slot = crea_slot(db, INIZIO, is_available=False)

    res = client.post("/bookings/", json={
        "user_id": utente["id"],
        "slot_id": slot.id,
        "duration_hours": 1,
        "service_type": "vod_review"
    })

    assert res.status_code == 400


def test_redenzione_pacchetto_azzera_prezzo_e_scala_credito(client, db):
    utente = crea_utente(client)
    slot_a = crea_slot(db, INIZIO)
    slot_b = crea_slot(db, INIZIO + timedelta(hours=1))

    pacchetto = Package(
        user_id=utente["id"], tipo="intro",
        sessioni_totali=2, sessioni_usate=0,
        durata_sessione_ore=2, prezzo_cents=7000
    )
    db.add(pacchetto)
    db.commit()
    db.refresh(pacchetto)

    res = client.post("/bookings/", json={
        "user_id": utente["id"],
        "slot_id": slot_a.id,
        "duration_hours": 2,
        "service_type": "team_building",
        "package_id": pacchetto.id
    })

    assert res.status_code == 200, res.text
    prenotazione = res.json()
    assert prenotazione["price_cents"] == 0
    assert prenotazione["package_id"] == pacchetto.id

    db.refresh(pacchetto)
    assert pacchetto.sessioni_usate == 1


def test_redenzione_pacchetto_esaurito_viene_rifiutata(client, db):
    utente = crea_utente(client)
    slot_a = crea_slot(db, INIZIO)
    crea_slot(db, INIZIO + timedelta(hours=1))

    pacchetto = Package(
        user_id=utente["id"], tipo="intro",
        sessioni_totali=1, sessioni_usate=1,  # già tutto usato
        durata_sessione_ore=2, prezzo_cents=7000
    )
    db.add(pacchetto)
    db.commit()
    db.refresh(pacchetto)

    res = client.post("/bookings/", json={
        "user_id": utente["id"],
        "slot_id": slot_a.id,
        "duration_hours": 2,
        "service_type": "team_building",
        "package_id": pacchetto.id
    })

    assert res.status_code == 400


def test_cancellazione_self_service_libera_entrambi_gli_slot(client, db):
    utente = crea_utente(client)
    primo = crea_slot(db, INIZIO)
    secondo = crea_slot(db, INIZIO + timedelta(hours=1))

    prenotazione = client.post("/bookings/", json={
        "user_id": utente["id"],
        "slot_id": primo.id,
        "duration_hours": 2,
        "service_type": "vod_review"
    }).json()

    token = crea_token_studente(utente["id"], utente["email"])
    res = client.patch(
        f"/bookings/{prenotazione['id']}/cancella",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200, res.text
    assert res.json()["status"] == "cancelled"

    db.refresh(primo)
    db.refresh(secondo)
    assert primo.is_available is True
    assert secondo.is_available is True


def test_cancellazione_rifiutata_per_prenotazione_di_un_altro(client, db):
    proprietario = crea_utente(client, email="proprietario@example.com")
    altro = crea_utente(client, email="altro@example.com")
    slot = crea_slot(db, INIZIO)

    prenotazione = client.post("/bookings/", json={
        "user_id": proprietario["id"],
        "slot_id": slot.id,
        "duration_hours": 1,
        "service_type": "vod_review"
    }).json()

    token_altro = crea_token_studente(altro["id"], altro["email"])
    res = client.patch(
        f"/bookings/{prenotazione['id']}/cancella",
        headers={"Authorization": f"Bearer {token_altro}"}
    )

    assert res.status_code == 403


def test_cancellazione_richiede_login(client, db):
    utente = crea_utente(client)
    slot = crea_slot(db, INIZIO)
    prenotazione = client.post("/bookings/", json={
        "user_id": utente["id"],
        "slot_id": slot.id,
        "duration_hours": 1,
        "service_type": "vod_review"
    }).json()

    res = client.patch(f"/bookings/{prenotazione['id']}/cancella")

    assert res.status_code == 401


def test_doppia_cancellazione_rifiutata(client, db):
    utente = crea_utente(client)
    slot = crea_slot(db, INIZIO)
    prenotazione = client.post("/bookings/", json={
        "user_id": utente["id"],
        "slot_id": slot.id,
        "duration_hours": 1,
        "service_type": "vod_review"
    }).json()

    token = crea_token_studente(utente["id"], utente["email"])
    headers = {"Authorization": f"Bearer {token}"}

    primo_tentativo = client.patch(f"/bookings/{prenotazione['id']}/cancella", headers=headers)
    secondo_tentativo = client.patch(f"/bookings/{prenotazione['id']}/cancella", headers=headers)

    assert primo_tentativo.status_code == 200
    assert secondo_tentativo.status_code == 400
