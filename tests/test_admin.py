# Copre DELETE /admin/clienti/{id} (backend/routers/admin.py), l'endpoint
# che implementa il diritto alla cancellazione (Art. 17 GDPR): deve
# eliminare cliente, prenotazioni, recensioni, note tecniche e pacchetti
# collegati, e liberare lo slot di ogni prenotazione ancora "confirmed".
# Vedi tests/conftest.py per come sono preparati client/db e perché le
# integrazioni esterne sono finte in tutti questi test.

from datetime import datetime

from backend.models.slots import Slot
from backend.models.users import User
from backend.models.booking import Booking
from backend.models.client_note import ClientNote
from backend.models.package import Package
from conftest import admin_headers

INIZIO = datetime(2030, 1, 7, 12, 0, 0)


def crea_utente(client, nome="Mario Rossi", email="mario@example.com"):
    res = client.post("/users/", json={
        "nome": nome, "email": email, "categoria": "senior",
        "discord_tag": "mario#0001", "telefono": None
    }).json()
    # POST /users/ restituisce solo {"id": ...} — l'email va riattaccata qui
    # per i test che devono mandarla anche a POST /bookings/ (vedi
    # BookingCreate.email in backend/schemas/booking.py).
    return {**res, "email": email}


def test_elimina_cliente_rimuove_tutti_i_dati_collegati(client, db):
    utente = crea_utente(client)

    slot = Slot(start_time=INIZIO, duration_hours=1, is_available=True)
    db.add(slot)
    db.commit()
    db.refresh(slot)

    prenotazione = client.post("/bookings/", json={
        "user_id": utente["id"],
        "email": utente["email"],
        "slot_id": slot.id,
        "duration_hours": 1,
        "service_type": "vod_review"
    }).json()

    # Nota tecnica e pacchetto assegnati dall'admin, per verificare che
    # l'eliminazione li travolga entrambi insieme al cliente.
    client.post(f"/admin/clienti/{utente['id']}/note", headers=admin_headers(), json={"nota": "Attenzione ai turni veloci"})
    client.post("/admin/pacchetti", headers=admin_headers(), json={"user_id": utente["id"], "tipo": "intro"})

    res = client.delete(f"/admin/clienti/{utente['id']}", headers=admin_headers())
    assert res.status_code == 200, res.text

    assert db.query(User).filter(User.id == utente["id"]).first() is None
    assert db.query(Booking).filter(Booking.id == prenotazione["id"]).first() is None
    assert db.query(ClientNote).filter(ClientNote.user_id == utente["id"]).count() == 0
    assert db.query(Package).filter(Package.user_id == utente["id"]).count() == 0

    # Lo slot occupato dalla prenotazione "confirmed" deve tornare libero,
    # esattamente come farebbe una cancellazione singola (vedi
    # libera_slot_prenotazione in backend/services/booking_service.py).
    db.refresh(slot)
    assert slot.is_available is True


def test_elimina_cliente_inesistente_restituisce_404(client, db):
    res = client.delete("/admin/clienti/9999", headers=admin_headers())
    assert res.status_code == 404


def test_elimina_cliente_richiede_login_admin(client, db):
    utente = crea_utente(client)
    res = client.delete(f"/admin/clienti/{utente['id']}")
    assert res.status_code == 401


def test_export_csv_richiede_admin(client, db):
    res = client.get("/admin/export/csv")
    assert res.status_code == 401


def test_export_csv_contiene_le_prenotazioni(client, db):
    utente = crea_utente(client, nome="Federica Test", email="federica.test@example.com")

    slot = Slot(start_time=INIZIO, duration_hours=1, is_available=True)
    db.add(slot)
    db.commit()
    db.refresh(slot)

    client.post("/bookings/", json={
        "user_id": utente["id"],
        "email": utente["email"],
        "slot_id": slot.id,
        "duration_hours": 1,
        "service_type": "vod_review"
    })

    res = client.get("/admin/export/csv", headers=admin_headers())

    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "attachment" in res.headers["content-disposition"]

    corpo = res.content.decode("utf-8-sig")  # BOM (vedi export_csv in admin.py), va tolto per confrontare il testo
    assert "Federica Test" in corpo
    assert "federica.test@example.com" in corpo
