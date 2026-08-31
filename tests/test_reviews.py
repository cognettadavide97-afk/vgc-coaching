# Copre il flusso recensioni end-to-end: invio pubblico (con token) →
# approvazione admin → comparsa nella vetrina pubblica. Vedi
# backend/models/review.py per il perché "approvata" esiste (una recensione
# non è pubblica finché il coach non la approva) e tests/conftest.py per
# come sono preparati client/db.

from datetime import datetime

from backend.models.slots import Slot
from backend.models.booking import Booking
from backend.services.auth_service import crea_token

INIZIO = datetime(2030, 1, 7, 12, 0, 0)


def crea_prenotazione_con_token(client, db, nome="Mario Rossi", email="mario@example.com"):
    utente = client.post("/users/", json={
        "nome": nome, "email": email, "categoria": "senior",
        "discord_tag": None, "telefono": None
    }).json()

    slot = Slot(start_time=INIZIO, duration_hours=1, is_available=True)
    db.add(slot)
    db.commit()
    db.refresh(slot)

    prenotazione = client.post("/bookings/", json={
        "user_id": utente["id"],
        "email": email,
        "slot_id": slot.id,
        "duration_hours": 1,
        "service_type": "vod_review"
    }).json()

    # review_token non è mai esposto via API (vedi BookingResponse in
    # backend/schemas/booking.py) — lo leggiamo direttamente dal database,
    # simulando il link che il cliente riceve via email.
    db_booking = db.query(Booking).filter(Booking.id == prenotazione["id"]).first()
    return prenotazione, db_booking.review_token


def test_recensione_inviata_non_e_subito_pubblica(client, db):
    prenotazione, token = crea_prenotazione_con_token(client, db)

    res = client.post(f"/bookings/{prenotazione['id']}/recensione", json={
        "token": token, "voto": 5, "commento": "Ottima sessione!"
    })

    assert res.status_code == 200, res.text
    assert res.json()["approvata"] is False

    pubbliche = client.get("/bookings/recensioni/pubbliche")
    assert pubbliche.json() == []


def test_recensione_con_token_sbagliato_viene_rifiutata(client, db):
    prenotazione, _token_vero = crea_prenotazione_con_token(client, db)

    res = client.post(f"/bookings/{prenotazione['id']}/recensione", json={
        "token": "token-inventato", "voto": 5
    })

    assert res.status_code == 403


def test_doppia_recensione_rifiutata(client, db):
    prenotazione, token = crea_prenotazione_con_token(client, db)
    client.post(f"/bookings/{prenotazione['id']}/recensione", json={"token": token, "voto": 4})

    res = client.post(f"/bookings/{prenotazione['id']}/recensione", json={"token": token, "voto": 2})

    assert res.status_code == 400


def test_recensione_approvata_compare_nella_vetrina_pubblica(client, db):
    prenotazione, token = crea_prenotazione_con_token(client, db, nome="Mario Rossi")
    recensione = client.post(f"/bookings/{prenotazione['id']}/recensione", json={
        "token": token, "voto": 5, "commento": "Consigliatissimo"
    }).json()

    admin_token = crea_token("admin")
    headers = {"Authorization": f"Bearer {admin_token}"}

    approvazione = client.patch(
        f"/admin/recensioni/{recensione['id']}",
        headers=headers,
        json={"approvata": True}
    )
    assert approvazione.status_code == 200
    assert approvazione.json()["approvata"] is True

    pubbliche = client.get("/bookings/recensioni/pubbliche").json()
    assert len(pubbliche) == 1
    assert pubbliche[0]["nome_cliente"] == "Mario"  # solo il nome di battesimo, vedi lo schema ReviewPubblica
    assert pubbliche[0]["voto"] == 5
    assert "email" not in pubbliche[0]
    assert "booking_id" not in pubbliche[0]


def test_lista_admin_filtra_per_stato_approvazione(client, db):
    prenotazione, token = crea_prenotazione_con_token(client, db)
    recensione = client.post(f"/bookings/{prenotazione['id']}/recensione", json={
        "token": token, "voto": 3
    }).json()

    admin_token = crea_token("admin")
    headers = {"Authorization": f"Bearer {admin_token}"}

    in_attesa = client.get("/admin/recensioni?approvata=false", headers=headers).json()
    approvate = client.get("/admin/recensioni?approvata=true", headers=headers).json()

    assert len(in_attesa) == 1
    assert in_attesa[0]["id"] == recensione["id"]
    assert approvate == []


def test_admin_endpoints_richiedono_login(client, db):
    res = client.get("/admin/recensioni")
    assert res.status_code == 401
