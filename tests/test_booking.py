# Copre il cuore del progetto: create_booking in backend/routers/booking.py
# (vedi i commenti lì per il "perché" della logica) e la cancellazione
# self-service. Vedi tests/conftest.py per come sono preparati client/db e
# perché le integrazioni esterne sono finte in tutti questi test.

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import event

import backend.routers.booking as booking_router
import backend.services.calendar_service as calendar_service
from backend.models.booking import Booking
from backend.models.package import Package
from conftest import TEST_ENGINE, admin_headers, apri_ore, crea_slot, iso, studente_cookies

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
# datetime.now()) e che le ore successive siano libere per i test sulle
# sessioni da 2 ore. Le ore diventano prenotabili con apri_ore (conftest.py),
# che crea la regola settimanale che le prevede: dal pezzo 4.4 le ore in
# vendita si calcolano dalle regole (services/disponibilita_service.py).
INIZIO = rome_naive_utc(2030, 1, 7, 15)


def prenota(client, utente, inizio, durata=1):
    return client.post("/bookings/", json={
        "user_id": utente["id"],
        "email": utente["email"],
        "start_time": iso(inizio),
        "duration_hours": durata,
        "service_type": "vod_review"
    })


def test_prenotazione_1_ora(client, db):
    utente = crea_utente(client)
    apri_ore(db, INIZIO)

    res = prenota(client, utente, INIZIO)

    assert res.status_code == 200, res.text
    prenotazione = res.json()
    # Prenotata per orario: nessuno slot collegato.
    assert prenotazione["slot_id"] is None
    assert prenotazione["slot_id_secondario"] is None
    assert prenotazione["price_cents"] == 2000  # 20€/ora, vedi TABELLA_PREZZI in booking.py
    assert prenotazione["status"] == "confirmed"
    assert db.query(Booking).one().start_time == INIZIO


def test_prenotazione_nel_passato_viene_rifiutata(client, db):
    # Una regola prevede quell'ora ogni settimana, anche nelle settimane già
    # passate: senza il controllo in create_booking una richiesta diretta
    # confermerebbe una sessione impossibile.
    utente = crea_utente(client)
    passato = rome_naive_utc(2020, 1, 6, 15)
    apri_ore(db, passato)

    res = prenota(client, utente, passato)

    assert res.status_code == 400
    assert "past" in res.json()["detail"]


def test_prenotazione_2_ore_occupa_due_ore_consecutive(client, db):
    utente = crea_utente(client)
    apri_ore(db, INIZIO, ore=2)

    res = prenota(client, utente, INIZIO, durata=2)

    assert res.status_code == 200, res.text
    assert res.json()["price_cents"] == 4000


def test_prenotazione_2_ore_alle_17_con_la_regola_15_19(client, db):
    utente = crea_utente(client)
    apri_ore(db, rome_naive_utc(2030, 1, 7, 15), ore=4)

    res = prenota(client, utente, rome_naive_utc(2030, 1, 7, 17), durata=2)

    assert res.status_code == 200, res.text


def test_prenotazione_2_ore_alle_16_con_la_regola_15_19_e_rifiutata(client, db):
    # Le sessioni da 2 ore partono ogni 2 ore dall'inizio della regola: con
    # 15-19 alle 15 e alle 17, mai alle 16, che lascerebbe isolate le ore ai
    # lati (vedi calcola_disponibilita). Anche se le 16 e le 17 sono libere,
    # il backend deve rifiutare la richiesta.
    utente = crea_utente(client)
    apri_ore(db, rome_naive_utc(2030, 1, 7, 15), ore=4)

    res = prenota(client, utente, rome_naive_utc(2030, 1, 7, 16), durata=2)

    assert res.status_code == 400
    assert db.query(Booking).count() == 0


def test_prenotazione_2_ore_fallisce_se_l_ora_successiva_non_e_in_vendita(client, db):
    utente = crea_utente(client)
    # La regola ha un'ora sola: non esiste l'ora successiva.
    apri_ore(db, INIZIO)

    res = prenota(client, utente, INIZIO, durata=2)

    assert res.status_code == 400
    assert db.query(Booking).count() == 0


def test_prenotazione_2_ore_fallisce_se_l_ora_successiva_e_gia_presa(client, db):
    utente = crea_utente(client)
    altro = crea_utente(client, email="altro@example.com")
    apri_ore(db, INIZIO, ore=2)
    assert prenota(client, altro, INIZIO + timedelta(hours=1)).status_code == 200

    res = prenota(client, utente, INIZIO, durata=2)

    assert res.status_code == 400
    assert db.query(Booking).count() == 1


def test_ora_gia_presa_viene_rifiutata(client, db):
    utente = crea_utente(client)
    altro = crea_utente(client, email="altro@example.com")
    apri_ore(db, INIZIO)
    assert prenota(client, altro, INIZIO).status_code == 200

    res = prenota(client, utente, INIZIO)

    assert res.status_code == 400
    assert res.json()["detail"] == "Slot not available"


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
    apri_ore(db, INIZIO)

    res = client.post("/bookings/", json={
        "user_id": vittima["id"],
        "email": "attaccante-idor@example.com",  # non l'email della vittima
        "start_time": iso(INIZIO),
        "duration_hours": 1,
        "service_type": "vod_review"
    })

    assert res.status_code == 403
    assert db.query(Booking).count() == 0


def test_prenotazione_guest_senza_email_restituisce_422(client, db):
    """
    REVISIONE_2026-09-01.md, ritrovamento R14: BookingCreate.email è
    dichiarata Optional, ma per il guest checkout è di fatto obbligatoria —
    senza, il confronto "user.email != booking.email" è sempre vero e la
    richiesta veniva rifiutata con un 403 "user_id and email do not match".

    Quel 403 descriveva un problema diverso da quello reale: chi integra
    l'API leggeva "le due cose non combaciano" mentre il vero motivo era
    "manca un campo obbligatorio", e su /docs vedeva un campo facoltativo
    che facoltativo non è. Deve invece arrivare un 422, il codice che
    FastAPI usa per un input malformato.

    Nota: l'email resta opzionale nello SCHEMA di proposito, perché lo
    studente loggato con Discord legittimamente non la manda — la sua
    identità viene dal token. L'obbligo vale solo sul ramo guest, quindi va
    espresso nel router e non in Pydantic.
    """
    utente = crea_utente(client, email="guest-senza-email@example.com")
    apri_ore(db, INIZIO)

    res = client.post("/bookings/", json={
        "user_id": utente["id"],
        # "email" deliberatamente assente
        "start_time": iso(INIZIO),
        "duration_hours": 1,
        "service_type": "vod_review"
    })

    assert res.status_code == 422, (
        f"atteso 422 per email mancante, ricevuto {res.status_code}: {res.text}"
    )
    assert "email" in res.json()["detail"].lower()
    assert db.query(Booking).count() == 0


def test_redenzione_pacchetto_azzera_prezzo_e_scala_credito(client, db):
    utente = crea_utente(client)
    # Due ore consecutive in vendita: la sessione da 2 ore le occupa entrambe.
    apri_ore(db, INIZIO, ore=2)

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
            "start_time": iso(INIZIO),
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
    apri_ore(db, INIZIO, ore=2)

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
        "start_time": iso(INIZIO),
        "duration_hours": 2,
        "service_type": "team_building",
        "package_id": pacchetto.id
    })

    assert res.status_code == 401


def test_redenzione_pacchetto_esaurito_viene_rifiutata(client, db):
    utente = crea_utente(client)
    apri_ore(db, INIZIO, ore=2)

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
            "start_time": iso(INIZIO),
            "duration_hours": 2,
            "service_type": "team_building",
            "package_id": pacchetto.id
        }
    )

    assert res.status_code == 400


def test_credito_pacchetto_non_si_spende_due_volte(client, db):
    # Race condition sul credito: due richieste simultanee dello stesso
    # cliente (doppio clic, due schede) passano entrambe il controllo "ha
    # ancora sessioni?" prima che una delle due scriva di averne usata una.
    # Nella suite le richieste arrivano una alla volta, quindi l'incrocio
    # va provocato: l'"intruso" qui sotto è un listener che scatta subito
    # prima che create_booking scali il credito, cioè DOPO il controllo, e
    # consuma l'ultima sessione come farebbe la richiesta concorrente.
    # La prenotazione deve essere rifiutata: col vecchio `+= 1` sull'oggetto
    # letto prima passava, e il pacchetto da 1 sessione ne pagava 2.
    utente = crea_utente(client)
    apri_ore(db, INIZIO, ore=2)

    pacchetto = Package(
        user_id=utente["id"], tipo="intro",
        sessioni_totali=1, sessioni_usate=0,
        durata_sessione_ore=2, prezzo_cents=7000
    )
    db.add(pacchetto)
    db.commit()
    id_pacchetto = pacchetto.id

    scattato = []

    def intruso(conn, cursor, statement, parameters, context, executemany):
        if not scattato and statement.lstrip().upper().startswith("UPDATE PACKAGES"):
            scattato.append(True)
            # Cursore separato sulla stessa connessione (StaticPool): la
            # scrittura entra nella stessa transazione della richiesta,
            # come una richiesta concorrente già confermata.
            altro = conn.connection.cursor()
            altro.execute(
                "UPDATE packages SET sessioni_usate = sessioni_totali WHERE id = ?",
                (id_pacchetto,)
            )
            altro.close()

    event.listen(TEST_ENGINE, "before_cursor_execute", intruso)
    try:
        res = client.post(
            "/bookings/",
            cookies=studente_cookies(utente["id"], utente["email"]),
            json={
                "user_id": utente["id"],
                "start_time": iso(INIZIO),
                "duration_hours": 2,
                "service_type": "team_building",
                "package_id": id_pacchetto
            }
        )
    finally:
        event.remove(TEST_ENGINE, "before_cursor_execute", intruso)

    assert scattato, "l'intruso non è scattato: il test non prova nulla"
    assert res.status_code == 400, res.text
    assert "no sessions left" in res.json()["detail"]
    assert db.query(Booking).count() == 0


def test_redenzione_pacchetto_di_un_altro_utente_viene_rifiutata(client, db):
    # Il vero scenario di furto: un attaccante loggato con IL PROPRIO
    # account Discord (token valido, ma per un altro utente) prova a usare
    # il package_id di una vittima, magari scoperto da
    # GET /users/pacchetti-attivi?email=vittima@... — deve fallire, perché
    # il controllo confronta package.user_id con l'id nel TOKEN, non con
    # user_id dichiarato nel body.
    vittima = crea_utente(client, email="vittima@example.com")
    attaccante = crea_utente(client, email="attaccante@example.com")
    apri_ore(db, INIZIO, ore=2)

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
            "start_time": iso(INIZIO),
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


def test_cancellazione_self_service_libera_entrambi_gli_slot_di_una_pagina_vecchia(client, db):
    # Le pagine vecchie, rimaste nella cache dei browser, prenotano ancora
    # per slot: la prenotazione li segna occupati e la cancellazione deve
    # liberarli tutti e due, o la loro lista smetterebbe di offrirli.
    utente = crea_utente(client)
    apri_ore(db, INIZIO, ore=2)
    primo = crea_slot(db, INIZIO)
    secondo = crea_slot(db, INIZIO + timedelta(hours=1))

    prenotazione = client.post("/bookings/", json={
        "user_id": utente["id"],
        "email": utente["email"],
        "slot_id": primo.id,
        "duration_hours": 2,
        "service_type": "vod_review"
    }).json()
    db.refresh(primo)
    db.refresh(secondo)
    assert prenotazione["slot_id"] == primo.id
    assert prenotazione["slot_id_secondario"] == secondo.id
    assert primo.is_available is False
    assert secondo.is_available is False

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
    apri_ore(db, INIZIO)

    prenotazione = client.post("/bookings/", json={
        "user_id": utente["id"],
        "email": utente["email"],
        "start_time": iso(INIZIO),
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
    apri_ore(db, INIZIO)

    prenotazione = client.post("/bookings/", json={
        "user_id": proprietario["id"],
        "email": proprietario["email"],
        "start_time": iso(INIZIO),
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
    apri_ore(db, INIZIO)
    prenotazione = client.post("/bookings/", json={
        "user_id": utente["id"],
        "email": utente["email"],
        "start_time": iso(INIZIO),
        "duration_hours": 1,
        "service_type": "vod_review"
    }).json()

    res = client.patch(f"/bookings/{prenotazione['id']}/cancella")

    assert res.status_code == 401


def test_doppia_cancellazione_rifiutata(client, db):
    utente = crea_utente(client)
    apri_ore(db, INIZIO)
    prenotazione = client.post("/bookings/", json={
        "user_id": utente["id"],
        "email": utente["email"],
        "start_time": iso(INIZIO),
        "duration_hours": 1,
        "service_type": "vod_review"
    }).json()

    cookies = studente_cookies(utente["id"], utente["email"])

    primo_tentativo = client.patch(f"/bookings/{prenotazione['id']}/cancella", cookies=cookies)
    secondo_tentativo = client.patch(f"/bookings/{prenotazione['id']}/cancella", cookies=cookies)

    assert primo_tentativo.status_code == 200
    assert secondo_tentativo.status_code == 400


# ─── RESTITUZIONE DEL CREDITO (decisione P7) ─────────────────
# Il credito torna a ogni cancellazione di una prenotazione confermata,
# dal cliente o dal pannello; il no-show lo consuma per sempre, anche se il
# coach in seguito lo cambia in cancelled. Regola che lo tiene in piedi:
# sessioni_usate = prenotazioni del pacchetto confermate o no-show.

def prenota_con_pacchetto(client, db):
    """Utente con pacchetto da 2 sessioni da 1 ora, già usato una volta per una prenotazione futura."""
    utente = crea_utente(client)
    apri_ore(db, INIZIO)
    pacchetto = Package(
        user_id=utente["id"], tipo="intro",
        sessioni_totali=2, sessioni_usate=0,
        durata_sessione_ore=1, prezzo_cents=7000
    )
    db.add(pacchetto)
    db.commit()
    cookies = studente_cookies(utente["id"], utente["email"])
    res = client.post("/bookings/", cookies=cookies, json={
        "user_id": utente["id"],
        "start_time": iso(INIZIO),
        "duration_hours": 1,
        "service_type": "vod_review",
        "package_id": pacchetto.id
    })
    assert res.status_code == 200, res.text
    db.refresh(pacchetto)
    assert pacchetto.sessioni_usate == 1
    return res.json(), pacchetto, cookies


def test_cancellazione_del_cliente_restituisce_il_credito(client, db):
    prenotazione, pacchetto, cookies = prenota_con_pacchetto(client, db)

    res = client.patch(f"/bookings/{prenotazione['id']}/cancella", cookies=cookies)

    assert res.status_code == 200, res.text
    db.refresh(pacchetto)
    assert pacchetto.sessioni_usate == 0
    attivi = client.get("/users/pacchetti-attivi", cookies=cookies).json()
    assert attivi[0]["sessioni_residue"] == 2


def test_cancellazione_dal_pannello_restituisce_il_credito(client, db):
    prenotazione, pacchetto, _ = prenota_con_pacchetto(client, db)

    res = client.patch(
        f"/admin/prenotazioni/{prenotazione['id']}/stato",
        headers=admin_headers(), json={"nuovo_stato": "cancelled"}
    )

    assert res.status_code == 200, res.text
    db.refresh(pacchetto)
    assert pacchetto.sessioni_usate == 0


def test_no_show_consuma_il_credito_anche_se_poi_cancellato(client, db):
    prenotazione, pacchetto, _ = prenota_con_pacchetto(client, db)
    url = f"/admin/prenotazioni/{prenotazione['id']}/stato"

    assert client.patch(url, headers=admin_headers(), json={"nuovo_stato": "no_show"}).status_code == 200
    db.refresh(pacchetto)
    assert pacchetto.sessioni_usate == 1

    assert client.patch(url, headers=admin_headers(), json={"nuovo_stato": "cancelled"}).status_code == 200
    db.refresh(pacchetto)
    assert pacchetto.sessioni_usate == 1


# ─── EMAIL CON MAIUSCOLE (voce 9) ────────────────────────────
# Ogni email entra in minuscolo (EmailNormalizzata in backend/schemas/users.py):
# registrazione e prenotazione confrontano così lo stesso testo.

def test_prenota_chi_scrive_il_dominio_con_la_maiuscola(client, db):
    # EmailStr metteva in minuscolo solo il dominio dell'utente salvato,
    # mentre la prenotazione riceveva il testo originale: 403 alla prima
    # prenotazione, su qualunque database.
    utente = crea_utente(client, email="mario@Example.com")
    apri_ore(db, INIZIO)

    res = client.post("/bookings/", json={
        "user_id": utente["id"],
        "email": "mario@Example.com",
        "start_time": iso(INIZIO),
        "duration_hours": 1,
        "service_type": "vod_review"
    })

    assert res.status_code == 200, res.text


def test_cliente_che_torna_con_la_maiuscola_prenota_sullo_stesso_account(client, db):
    # Il telefono mette la maiuscola alla prima lettera: stesso account,
    # prenotazione riuscita.
    primo = crea_utente(client, email="mario@example.com")
    di_nuovo = crea_utente(client, email="Mario@example.com")
    apri_ore(db, INIZIO)

    res = client.post("/bookings/", json={
        "user_id": di_nuovo["id"],
        "email": "Mario@example.com",
        "start_time": iso(INIZIO),
        "duration_hours": 1,
        "service_type": "vod_review"
    })

    assert di_nuovo["id"] == primo["id"]
    assert res.status_code == 200, res.text


# ─── Evento Calendar dopo il commit (voci 11-12) ──────────────
#
# Le riserve di create_booking tengono un lock sulle righe che scrivono
# (allora slot e pacchetto, oggi ore vendute e pacchetto) fino al commit.
# Con Google Calendar chiamato prima del commit, una risposta lenta (fino a
# 60 s) faceva aspettare ogni altra prenotazione della stessa ora o dello
# stesso pacchetto, e oltre i 50 s MySQL rispondeva con un
# errore 1205, cioè un 500. SQLite non ha lock di riga: la contesa vera si
# prova sul MySQL locale. Qui si fissano l'ordine e cosa succede dopo.

def prenota_un_ora(client, db):
    utente = crea_utente(client)
    apri_ore(db, INIZIO)
    return client.post("/bookings/", json={
        "user_id": utente["id"],
        "email": utente["email"],
        "start_time": iso(INIZIO),
        "duration_hours": 1,
        "service_type": "vod_review"
    })


def test_l_evento_calendar_si_crea_solo_a_prenotazione_salvata(client, db, monkeypatch):
    utente = crea_utente(client)
    apri_ore(db, INIZIO)
    sequenza = []

    def registra_commit(conn):
        sequenza.append("commit")

    def evento_finto(**kwargs):
        # Cosa trova Google quando viene chiamato: la prenotazione deve
        # esistere già, e il commit deve essere già avvenuto.
        sequenza.append("calendar")
        sequenza.append("prenotazione presente" if db.query(Booking).count() == 1 else "prenotazione assente")
        return "evento_google_123"

    monkeypatch.setattr(booking_router, "crea_evento_calendario", evento_finto)

    event.listen(TEST_ENGINE, "commit", registra_commit)
    try:
        res = client.post("/bookings/", json={
            "user_id": utente["id"],
            "email": utente["email"],
            "start_time": iso(INIZIO),
            "duration_hours": 1,
            "service_type": "vod_review"
        })
    finally:
        event.remove(TEST_ENGINE, "commit", registra_commit)

    assert res.status_code == 200, res.text
    assert sequenza[:3] == ["commit", "calendar", "prenotazione presente"], sequenza


def test_l_id_dell_evento_si_salva_sulla_prenotazione(client, db, monkeypatch):
    monkeypatch.setattr(booking_router, "crea_evento_calendario", lambda **kwargs: "evento_google_123")

    res = prenota_un_ora(client, db)

    assert res.status_code == 200, res.text
    assert db.query(Booking).one().calendar_event_id == "evento_google_123"


def test_se_l_evento_non_si_crea_il_coach_viene_avvisato(client, db, monkeypatch):
    """La prenotazione resta valida, ma senza avviso il coach la scoprirebbe mancante solo guardando l'agenda."""
    avvisi = []
    monkeypatch.setattr(booking_router, "crea_evento_calendario", lambda **kwargs: None)
    monkeypatch.setattr(booking_router, "invia_alert_sistema", lambda titolo, descrizione: avvisi.append((titolo, descrizione)))

    res = prenota_un_ora(client, db)

    assert res.status_code == 200, res.text
    prenotazione = db.query(Booking).one()
    assert prenotazione.status == "confirmed"
    assert prenotazione.calendar_event_id is None
    assert len(avvisi) == 1
    titolo, descrizione = avvisi[0]
    assert f"prenotazione {prenotazione.id}" in descrizione
    assert "cliente@example.com" not in titolo + descrizione


def test_una_prenotazione_cancellata_mentre_si_crea_l_evento_non_lo_lascia_in_agenda(client, db, monkeypatch):
    """
    Finché Google non risponde la prenotazione esiste senza id evento: una
    cancellazione arrivata in quel momento (il cliente che ricarica la
    pagina, il coach dal pannello) non trova niente da eliminare. L'evento
    creato subito dopo va eliminato, o resterebbe in agenda per una
    sessione che non esiste più.
    """
    eliminati = []

    def evento_e_cancellazione(**kwargs):
        prenotazione = db.query(Booking).first()
        if prenotazione:
            prenotazione.status = "cancelled"
            db.commit()
        return "evento_google_123"

    monkeypatch.setattr(booking_router, "crea_evento_calendario", evento_e_cancellazione)
    monkeypatch.setattr(booking_router, "elimina_evento_calendario", lambda event_id: eliminati.append(event_id) or True)

    res = prenota_un_ora(client, db)

    assert res.status_code == 200, res.text
    assert eliminati == ["evento_google_123"]
    prenotazione = db.query(Booking).one()
    db.refresh(prenotazione)
    assert prenotazione.status == "cancelled"
    assert prenotazione.calendar_event_id is None


def test_la_prenotazione_crea_un_evento_senza_email_note_e_cognome(client, db, monkeypatch):
    """
    Con la funzione vera di calendar_service e non la finta di conftest:
    è anche la prova che create_booking la chiama con la firma giusta. Una
    finta con **kwargs accetta qualunque argomento, e un errore di firma
    diventerebbe un 500 solo in produzione, a prenotazione già salvata.
    """
    corpi = []

    class ServizioFinto:
        def events(self):
            return self

        def insert(self, calendarId=None, body=None):
            corpi.append(body)
            return self

        def execute(self):
            return {"id": "evento_google_123", "htmlLink": "https://calendar.google.com/evento"}

    monkeypatch.setattr(booking_router, "crea_evento_calendario", calendar_service.crea_evento_calendario)
    monkeypatch.setattr(calendar_service, "get_calendar_service", lambda: ServizioFinto())

    utente = crea_utente(client)
    apri_ore(db, INIZIO)
    res = client.post("/bookings/", json={
        "user_id": utente["id"],
        "email": utente["email"],
        "start_time": iso(INIZIO),
        "duration_hours": 1,
        "service_type": "vod_review",
        "note_cliente": "Uso Trick Room con Indeedee-F"
    })

    assert res.status_code == 200, res.text
    assert len(corpi) == 1
    assert corpi[0]["summary"] == "Coaching VGC — Cliente"
    testo = corpi[0]["summary"] + corpi[0]["description"]
    for dato in ("cliente@example.com", "Trick Room", "Test"):
        assert dato not in testo, dato
    assert f"prenotazione {res.json()['id']}" in testo
    assert db.query(Booking).one().calendar_event_id == "evento_google_123"
