"""Le ore vendute: la guardia contro la doppia prenotazione della stessa ora (pezzo 4.3b, P9).

Ogni prenotazione non cancellata ha una riga in `ore_prenotate` per ogni
sua ora, e la chiave primaria sull'ora impedisce al database di venderla
due volte (vedi backend/models/ora_prenotata.py). Fino al 4.4 la riserva
sullo slot resta attiva: per vedere la nuova guardia al lavoro da sola, il
test della corsa mette un'altra prenotazione sulla stessa ora mentre la
richiesta è a metà, come farebbe una richiesta concorrente senza slot.
"""

from datetime import timedelta

from sqlalchemy import event

from backend.models.booking import Booking
from backend.models.ora_prenotata import OraPrenotata
from backend.models.slots import Slot
from backend.models.users import User
from conftest import TEST_ENGINE, admin_headers, crea_slot, studente_cookies

# Lunedì 7 gennaio 2030, 15:00 italiane (14:00 UTC, ora solare).
from test_booking import INIZIO


def utente_db(db, email="cliente@example.com"):
    utente = User(nome="Cliente Test", email=email, categoria="senior")
    db.add(utente)
    db.commit()
    db.refresh(utente)
    return utente


def prenota(client, utente, slot, durata=1):
    res = client.post("/bookings/", json={
        "user_id": utente.id, "email": utente.email, "slot_id": slot.id,
        "duration_hours": durata, "service_type": "vod_review"
    })
    assert res.status_code == 200, res.text
    return res.json()["id"]


def ore_di(db, booking_id):
    db.expire_all()
    return [o.inizio for o in db.query(OraPrenotata).filter(OraPrenotata.booking_id == booking_id)
            .order_by(OraPrenotata.inizio)]


def test_una_sessione_da_un_ora_occupa_la_sua_ora(client, db):
    utente = utente_db(db)
    slot = crea_slot(db, INIZIO)

    booking_id = prenota(client, utente, slot)

    assert ore_di(db, booking_id) == [INIZIO]


def test_una_sessione_da_due_ore_occupa_due_ore(client, db):
    utente = utente_db(db)
    slot = crea_slot(db, INIZIO)
    crea_slot(db, INIZIO + timedelta(hours=1))

    booking_id = prenota(client, utente, slot, durata=2)

    assert ore_di(db, booking_id) == [INIZIO, INIZIO + timedelta(hours=1)]


def test_la_cancellazione_del_cliente_libera_le_ore(client, db):
    utente = utente_db(db)
    slot = crea_slot(db, INIZIO)
    crea_slot(db, INIZIO + timedelta(hours=1))
    booking_id = prenota(client, utente, slot, durata=2)

    res = client.patch(f"/bookings/{booking_id}/cancella", cookies=studente_cookies(utente.id, utente.email))

    assert res.status_code == 200, res.text
    assert ore_di(db, booking_id) == []


def test_la_cancellazione_dal_pannello_libera_le_ore_e_il_no_show_le_tiene(client, db):
    utente = utente_db(db)
    no_show = prenota(client, utente, crea_slot(db, INIZIO))
    cancellata = prenota(client, utente, crea_slot(db, INIZIO + timedelta(days=1)))

    client.patch(f"/admin/prenotazioni/{no_show}/stato", json={"nuovo_stato": "no_show"}, headers=admin_headers())
    client.patch(f"/admin/prenotazioni/{cancellata}/stato", json={"nuovo_stato": "cancelled"}, headers=admin_headers())

    # Un no-show occupa ancora la sua ora: solo la cancellazione la libera.
    assert ore_di(db, no_show) == [INIZIO]
    assert ore_di(db, cancellata) == []


def test_un_ora_cancellata_si_puo_riprenotare(client, db):
    primo = utente_db(db)
    secondo = utente_db(db, email="secondo@example.com")
    slot = crea_slot(db, INIZIO)
    prima = prenota(client, primo, slot)
    client.patch(f"/bookings/{prima}/cancella", cookies=studente_cookies(primo.id, primo.email))

    seconda = prenota(client, secondo, slot)

    assert ore_di(db, seconda) == [INIZIO]


def test_il_diritto_all_oblio_elimina_anche_le_ore_di_un_no_show(client, db):
    # Le ore di un no-show restano: senza ON DELETE CASCADE la chiave
    # esterna bloccherebbe l'eliminazione del cliente (1451 su MySQL; qui
    # lo stesso rifiuto grazie al PRAGMA foreign_keys di conftest.py).
    utente = utente_db(db)
    booking_id = prenota(client, utente, crea_slot(db, INIZIO))
    client.patch(f"/admin/prenotazioni/{booking_id}/stato", json={"nuovo_stato": "no_show"}, headers=admin_headers())

    res = client.delete(f"/admin/clienti/{utente.id}", headers=admin_headers())

    assert res.status_code == 200, res.text
    db.expire_all()
    assert db.query(OraPrenotata).count() == 0


def test_la_stessa_ora_non_si_vende_due_volte(client, db):
    # Race condition: nella suite le richieste arrivano una alla volta, quindi
    # la richiesta concorrente va provocata. L'"intruso" scatta mentre
    # create_booking riserva lo slot e scrive, nella stessa transazione, la
    # prenotazione di un altro cliente sulla stessa ora: è ciò che succederà
    # dal 4.4, quando non ci sarà più uno slot a fermare la seconda richiesta.
    # Sul codice senza la guardia la prenotazione passava: due clienti alla
    # stessa ora.
    utente = utente_db(db)
    altro = utente_db(db, email="altro@example.com")
    slot = crea_slot(db, INIZIO)
    slot_altro = crea_slot(db, INIZIO + timedelta(days=7), is_available=False)
    # Stesso formato con cui SQLAlchemy salva le date su SQLite: con un
    # formato diverso le due ore sarebbero stringhe diverse e non si
    # scontrerebbero.
    inizio_sqlite = INIZIO.strftime("%Y-%m-%d %H:%M:%S.%f")

    scattato = []

    def intruso(conn, cursor, statement, parameters, context, executemany):
        if not scattato and statement.lstrip().upper().startswith("UPDATE SLOTS"):
            scattato.append(True)
            c = conn.connection.cursor()
            c.execute(
                "INSERT INTO bookings (user_id, slot_id, start_time, duration_hours, price_cents, "
                "service_type, status, reminder_sent, review_email_sent) "
                "VALUES (?, ?, ?, 1, 2000, 'vod_review', 'confirmed', 0, 0)",
                (altro.id, slot_altro.id, inizio_sqlite)
            )
            c.execute("INSERT INTO ore_prenotate (inizio, booking_id) VALUES (?, ?)",
                      (inizio_sqlite, c.lastrowid))
            c.close()

    event.listen(TEST_ENGINE, "before_cursor_execute", intruso)
    try:
        res = client.post("/bookings/", json={
            "user_id": utente.id, "email": utente.email, "slot_id": slot.id,
            "duration_hours": 1, "service_type": "vod_review"
        })
    finally:
        event.remove(TEST_ENGINE, "before_cursor_execute", intruso)

    assert scattato, "l'intruso non è scattato: il test non prova nulla"
    assert res.status_code == 400, res.text
    assert res.json()["detail"] == "Slot not available"
    # Il rifiuto annulla tutta la transazione, compresa la riserva dello
    # slot (e, qui, anche l'intruso, che vi era entrato).
    db.expire_all()
    assert db.query(Booking).filter(Booking.user_id == utente.id).count() == 0
    assert db.query(Slot).filter(Slot.id == slot.id).one().is_available is True
