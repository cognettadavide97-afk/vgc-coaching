# Copre il cuore del progetto: create_booking in backend/routers/booking.py
# (vedi i commenti lì per il "perché" della logica) e la cancellazione
# self-service. Vedi tests/conftest.py per come sono preparati client/db e
# perché le integrazioni esterne sono finte in tutti questi test.

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from backend.models.booking import Booking
from backend.models.package import Package
from conftest import crea_slot, studente_cookies

ROME_TZ = ZoneInfo("Europe/Rome")


def rome_naive_utc(anno, mese, giorno, ora):
    """Costruisce un datetime naive-UTC (come salvato nel DB, vedi backend/models/slots.py)
    a partire da un orario espresso in ora ITALIANA — serve per testare
    ORE_INIZIO_VALIDE_2H in backend/routers/booking.py, che ragiona in ora
    italiana, senza dover calcolare a mano l'offset UTC+1/+2 di ogni data."""
    return datetime(anno, mese, giorno, ora, tzinfo=ROME_TZ).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def crea_utente(client, email="cliente@example.com"):
    res = client.post("/users/", json={
        "nome": "Cliente Test",
        "email": email,
        "categoria": "senior",
        "discord_tag": "clientetest",
        "telefono": None
    })
    assert res.status_code == 200, res.text
    # POST /users/ restituisce solo {"id": ...} da quando risponde con
    # UserIdResponse invece di UserResponse (fix di sicurezza: non deve più
    # rivelare il profilo di un cliente esistente a chi ne indovina l'email,
    # vedi backend/schemas/users.py) — i test però conoscono già l'email
    # (l'hanno appena mandata), gliela riattacchiamo qui per comodità invece
    # di ripeterla ovunque serve studente_cookies(id, email).
    return {**res.json(), "email": email}


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
        "email": utente["email"],
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


def test_prenotazione_su_slot_passato_viene_rifiutata(client, db):
    # Uno slot mai prenotato resta is_available=True anche dopo che il suo
    # orario è passato (nessun job lo marca scaduto) — vedi il controllo
    # in create_booking, backend/routers/booking.py.
    utente = crea_utente(client)
    slot_passato = crea_slot(db, rome_naive_utc(2020, 1, 6, 15))

    res = client.post("/bookings/", json={
        "user_id": utente["id"],
        "email": utente["email"],
        "slot_id": slot_passato.id,
        "duration_hours": 1,
        "service_type": "vod_review"
    })

    assert res.status_code == 400


def test_prenotazione_2_ore_unisce_due_slot_adiacenti(client, db):
    utente = crea_utente(client)
    primo = crea_slot(db, INIZIO)
    secondo = crea_slot(db, INIZIO + timedelta(hours=1))

    res = client.post("/bookings/", json={
        "user_id": utente["id"],
        "email": utente["email"],
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
        "email": utente["email"],
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
        "email": utente["email"],
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
        "email": utente["email"],
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
        "email": utente["email"],
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
        "email": utente["email"],
        "slot_id": slot.id,
        "duration_hours": 1,
        "service_type": "vod_review"
    })

    assert res.status_code == 400


def test_prenotazione_guest_a_nome_di_un_altro_utente_viene_rifiutata(client, db):
    """
    Riproduce l'IDOR su booking.user_id (ANALISI_2026-08-31.md, Area
    Sicurezza/Backend): un guest non loggato manda lo user_id di un'altra
    persona (in produzione, una PK sequenziale banale da enumerare) insieme
    a un'email diversa dalla sua — non deve poter creare la prenotazione a
    nome della vittima (furto di identità: evento Calendar, email di
    conferma e limite di prenotazioni attive della vittima, tutti abusati
    senza che lei abbia fatto nulla).
    """
    vittima = crea_utente(client, email="vittima-idor@example.com")
    slot = crea_slot(db, INIZIO)

    res = client.post("/bookings/", json={
        "user_id": vittima["id"],
        "email": "attaccante-idor@example.com",  # non l'email della vittima
        "slot_id": slot.id,
        "duration_hours": 1,
        "service_type": "vod_review"
    })

    assert res.status_code == 403
    assert db.query(Booking).count() == 0


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

    # Usare un pacchetto richiede login Discord (vedi il controllo "if not
    # studente" su POST /bookings/ in backend/routers/booking.py): senza,
    # chiunque conoscesse user_id/package_id di un cliente vero avrebbe
    # potuto scalargli una sessione senza il suo consenso.
    res = client.post(
        "/bookings/",
        cookies=studente_cookies(utente["id"], utente["email"]),
        json={
            "user_id": utente["id"],
            "slot_id": slot_a.id,
            "duration_hours": 2,
            "service_type": "team_building",
            "package_id": pacchetto.id
        }
    )

    assert res.status_code == 200, res.text
    prenotazione = res.json()
    assert prenotazione["price_cents"] == 0
    assert prenotazione["package_id"] == pacchetto.id

    db.refresh(pacchetto)
    assert pacchetto.sessioni_usate == 1


def test_redenzione_pacchetto_senza_login_viene_rifiutata(client, db):
    # Copre proprio la falla chiusa da questo controllo: senza un token
    # studente valido, provare a prenotare con un package_id (anche vero,
    # anche di un altro utente) deve fallire con 401 — vedi il commento in
    # backend/routers/booking.py.
    utente = crea_utente(client)
    slot_a = crea_slot(db, INIZIO)
    crea_slot(db, INIZIO + timedelta(hours=1))

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
        "email": utente["email"],
        "slot_id": slot_a.id,
        "duration_hours": 2,
        "service_type": "team_building",
        "package_id": pacchetto.id
    })

    assert res.status_code == 401


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

    res = client.post(
        "/bookings/",
        cookies=studente_cookies(utente["id"], utente["email"]),
        json={
            "user_id": utente["id"],
            "slot_id": slot_a.id,
            "duration_hours": 2,
            "service_type": "team_building",
            "package_id": pacchetto.id
        }
    )

    assert res.status_code == 400


def test_redenzione_pacchetto_di_un_altro_utente_viene_rifiutata(client, db):
    # Il vero scenario di furto: un attaccante loggato con IL PROPRIO
    # account Discord (token valido, ma per un altro utente) prova a usare
    # il package_id di una vittima, magari scoperto da
    # GET /users/pacchetti-attivi?email=vittima@... — deve fallire, perché
    # il controllo confronta package.user_id con l'id nel TOKEN, non con
    # user_id dichiarato nel body.
    vittima = crea_utente(client, email="vittima@example.com")
    attaccante = crea_utente(client, email="attaccante@example.com")
    slot_a = crea_slot(db, INIZIO)
    crea_slot(db, INIZIO + timedelta(hours=1))

    pacchetto_vittima = Package(
        user_id=vittima["id"], tipo="intro",
        sessioni_totali=2, sessioni_usate=0,
        durata_sessione_ore=2, prezzo_cents=7000
    )
    db.add(pacchetto_vittima)
    db.commit()
    db.refresh(pacchetto_vittima)

    res = client.post(
        "/bookings/",
        cookies=studente_cookies(attaccante["id"], attaccante["email"]),
        json={
            "user_id": vittima["id"],  # l'attaccante dichiara la vittima come user_id...
            "slot_id": slot_a.id,
            "duration_hours": 2,
            "service_type": "team_building",
            "package_id": pacchetto_vittima.id  # ...e prova a usare il SUO pacchetto
        }
    )

    assert res.status_code == 404  # "Package not found": non è suo, anche se esiste davvero

    db.refresh(pacchetto_vittima)
    assert pacchetto_vittima.sessioni_usate == 0  # il credito della vittima resta intatto


def test_pacchetti_attivi_richiede_login_e_mostra_solo_i_propri(client, db):
    # Copre il fix gemello di quello sopra: GET /users/pacchetti-attivi non
    # accetta più un'email nella query string (chiunque poteva scoprire i
    # pacchetti di un altro), ma identifica l'utente dal token — vedi
    # backend/routers/users.py.
    vittima = crea_utente(client, email="vittima2@example.com")
    attaccante = crea_utente(client, email="attaccante2@example.com")

    pacchetto_vittima = Package(
        user_id=vittima["id"], tipo="intro",
        sessioni_totali=2, sessioni_usate=0,
        durata_sessione_ore=2, prezzo_cents=7000
    )
    db.add(pacchetto_vittima)
    db.commit()

    res_senza_login = client.get("/users/pacchetti-attivi")
    assert res_senza_login.status_code == 401

    res_attaccante = client.get(
        "/users/pacchetti-attivi",
        cookies=studente_cookies(attaccante["id"], attaccante["email"])
    )
    assert res_attaccante.status_code == 200
    assert res_attaccante.json() == []  # l'attaccante non vede i pacchetti della vittima

    res_vittima = client.get(
        "/users/pacchetti-attivi",
        cookies=studente_cookies(vittima["id"], vittima["email"])
    )
    assert res_vittima.status_code == 200
    assert len(res_vittima.json()) == 1


def test_cancellazione_self_service_libera_entrambi_gli_slot(client, db):
    utente = crea_utente(client)
    primo = crea_slot(db, INIZIO)
    secondo = crea_slot(db, INIZIO + timedelta(hours=1))

    prenotazione = client.post("/bookings/", json={
        "user_id": utente["id"],
        "email": utente["email"],
        "slot_id": primo.id,
        "duration_hours": 2,
        "service_type": "vod_review"
    }).json()

    res = client.patch(
        f"/bookings/{prenotazione['id']}/cancella",
        cookies=studente_cookies(utente["id"], utente["email"])
    )

    assert res.status_code == 200, res.text
    assert res.json()["status"] == "cancelled"

    db.refresh(primo)
    db.refresh(secondo)
    assert primo.is_available is True
    assert secondo.is_available is True


def test_cancellazione_self_service_non_espone_note_admin(client, db):
    """
    ANALISI_2026-08-31.md, Area Back-end: note_admin è documentato come
    "visibile solo al coach" (STATO_PROGETTO.md) — la risposta della
    cancellazione self-service non deve includerlo, altrimenti uno
    studente che cancella una propria prenotazione su cui il coach aveva
    scritto una nota privata se la ritroverebbe nel JSON di risposta.
    """
    utente = crea_utente(client)
    slot = crea_slot(db, INIZIO)

    prenotazione = client.post("/bookings/", json={
        "user_id": utente["id"],
        "email": utente["email"],
        "slot_id": slot.id,
        "duration_hours": 1,
        "service_type": "vod_review"
    }).json()

    # Simula il coach che scrive una nota privata prima che lo studente
    # cancelli.
    db_booking = db.query(Booking).filter(Booking.id == prenotazione["id"]).first()
    db_booking.note_admin = "Cliente difficile, tenere d'occhio i pagamenti"
    db.commit()

    res = client.patch(
        f"/bookings/{prenotazione['id']}/cancella",
        cookies=studente_cookies(utente["id"], utente["email"])
    )

    assert res.status_code == 200, res.text
    assert "note_admin" not in res.json()


def test_cancellazione_rifiutata_per_prenotazione_di_un_altro(client, db):
    proprietario = crea_utente(client, email="proprietario@example.com")
    altro = crea_utente(client, email="altro@example.com")
    slot = crea_slot(db, INIZIO)

    prenotazione = client.post("/bookings/", json={
        "user_id": proprietario["id"],
        "email": proprietario["email"],
        "slot_id": slot.id,
        "duration_hours": 1,
        "service_type": "vod_review"
    }).json()

    res = client.patch(
        f"/bookings/{prenotazione['id']}/cancella",
        cookies=studente_cookies(altro["id"], altro["email"])
    )

    assert res.status_code == 403


def test_cancellazione_richiede_login(client, db):
    utente = crea_utente(client)
    slot = crea_slot(db, INIZIO)
    prenotazione = client.post("/bookings/", json={
        "user_id": utente["id"],
        "email": utente["email"],
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
        "email": utente["email"],
        "slot_id": slot.id,
        "duration_hours": 1,
        "service_type": "vod_review"
    }).json()

    cookies = studente_cookies(utente["id"], utente["email"])

    primo_tentativo = client.patch(f"/bookings/{prenotazione['id']}/cancella", cookies=cookies)
    secondo_tentativo = client.patch(f"/bookings/{prenotazione['id']}/cancella", cookies=cookies)

    assert primo_tentativo.status_code == 200
    assert secondo_tentativo.status_code == 400
