# Copre GET /users/me/prenotazioni (backend/routers/users.py), lo storico
# che lo studente autenticato vede nella propria area. È un endpoint che
# legge dati personali filtrando per identità: la categoria che la
# checklist di sicurezza del progetto dice di controllare sempre, perché
# un filtro sbagliato non fa fallire nulla — mostra semplicemente a uno
# studente le prenotazioni di un altro.
#
# L'autenticazione passa dal cookie httpOnly "student_token", non da un
# header Authorization: vedi l'helper studente_cookies in tests/conftest.py.

from datetime import datetime, timedelta, timezone

from backend.models.users import User
from backend.models.booking import Booking
from conftest import crea_slot, studente_cookies

# Istante fisso invece di "adesso": le asserzioni sulla data formattata
# devono valere sempre, non solo il giorno in cui girano i test.
# 14:30 UTC di gennaio = 15:30 a Roma (CET, UTC+1).
GENNAIO = datetime(2026, 1, 15, 14, 30, tzinfo=timezone.utc).replace(tzinfo=None)


def crea_studente(db, email="studente@example.com", nome="Studente Test"):
    utente = User(nome=nome, email=email)
    db.add(utente)
    db.commit()
    db.refresh(utente)
    return utente


def crea_prenotazione(db, utente, slot, **campi):
    prenotazione = Booking(
        user_id=utente.id, slot_id=slot.id,
        duration_hours=campi.get("duration_hours", 1),
        price_cents=campi.get("price_cents", 2000),
        service_type=campi.get("service_type", "vod_review"),
        status=campi.get("status", "confirmed"),
    )
    db.add(prenotazione)
    db.commit()
    db.refresh(prenotazione)
    return prenotazione


# ─── Accesso ──────────────────────────────────────────────────

def test_prenotazioni_senza_login_rifiutate(client):
    risposta = client.get("/users/me/prenotazioni")

    assert risposta.status_code == 401


def test_prenotazioni_con_cookie_non_valido_rifiutate(client, db):
    utente = crea_studente(db)

    risposta = client.get(
        "/users/me/prenotazioni",
        cookies={"student_token": "non-e-un-token"}
    )

    assert risposta.status_code == 401


# ─── Filtro per identità ──────────────────────────────────────

def test_studente_vede_solo_le_proprie_prenotazioni(client, db):
    """Il controllo centrale di questo endpoint: due studenti con una
    prenotazione ciascuno, e nessuno dei due deve vedere quella dell'altro."""
    mio = crea_studente(db, email="mio@example.com", nome="Studente Mio")
    altro = crea_studente(db, email="altro@example.com", nome="Studente Altro")

    slot_mio = crea_slot(db, GENNAIO, is_available=False)
    slot_altro = crea_slot(db, GENNAIO + timedelta(hours=2), is_available=False)
    prenotazione_mia = crea_prenotazione(db, mio, slot_mio, service_type="vod_review")
    prenotazione_altrui = crea_prenotazione(db, altro, slot_altro, service_type="team_building")

    risposta = client.get(
        "/users/me/prenotazioni",
        cookies=studente_cookies(mio.id, mio.email)
    )

    assert risposta.status_code == 200
    dati = risposta.json()
    assert len(dati) == 1
    assert dati[0]["id"] == prenotazione_mia.id
    # Non basta contare: verifichiamo che l'id altrui non compaia proprio.
    assert prenotazione_altrui.id not in [p["id"] for p in dati]


def test_studente_senza_prenotazioni_riceve_lista_vuota(client, db):
    utente = crea_studente(db)

    risposta = client.get(
        "/users/me/prenotazioni",
        cookies=studente_cookies(utente.id, utente.email)
    )

    assert risposta.status_code == 200
    assert risposta.json() == []


# ─── Ordinamento e formato ────────────────────────────────────

def test_prenotazioni_ordinate_dalla_piu_recente(client, db):
    utente = crea_studente(db)
    # Inserite in ordine cronologico crescente, così un eventuale
    # ordinamento sbagliato (per id, o senza .desc()) le restituirebbe
    # nell'ordine opposto a quello atteso.
    slot_vecchio = crea_slot(db, GENNAIO - timedelta(days=7), is_available=False)
    slot_medio = crea_slot(db, GENNAIO, is_available=False)
    slot_nuovo = crea_slot(db, GENNAIO + timedelta(days=7), is_available=False)
    crea_prenotazione(db, utente, slot_vecchio)
    crea_prenotazione(db, utente, slot_medio)
    crea_prenotazione(db, utente, slot_nuovo)

    risposta = client.get(
        "/users/me/prenotazioni",
        cookies=studente_cookies(utente.id, utente.email)
    )

    dati = risposta.json()
    assert len(dati) == 3
    assert [p["data"] for p in dati] == ["22/01/2026", "15/01/2026", "08/01/2026"]


def test_prenotazione_esposta_con_i_campi_attesi(client, db):
    """La risposta è costruita a mano, senza response_model: nessuno
    schema Pydantic la valida, quindi i campi vanno controllati qui."""
    utente = crea_studente(db)
    slot = crea_slot(db, GENNAIO, duration_hours=2, is_available=False)
    prenotazione = crea_prenotazione(
        db, utente, slot,
        duration_hours=2, service_type="bo3_sparring", status="confirmed"
    )

    risposta = client.get(
        "/users/me/prenotazioni",
        cookies=studente_cookies(utente.id, utente.email)
    )

    voce = risposta.json()[0]
    assert voce == {
        "id": prenotazione.id,
        "servizio": "bo3_sparring",
        "stato": "confirmed",
        # 14:30 UTC in gennaio = 15:30 a Roma (CET, UTC+1).
        "data": "15/01/2026",
        "ora": "15:30",
        "durata_ore": 2,
        # L'offset esplicito è ciò che permette al frontend di stabilire se
        # la sessione è passata senza reinterpretare le stringhe formattate:
        # senza "+00:00" il browser leggerebbe l'orario come locale.
        "start_time_iso": "2026-01-15T14:30:00+00:00",
    }
    # Le note riservate al coach non devono comparire nella risposta.
    assert "note_admin" not in voce


def test_ora_legale_convertita_con_offset_estivo(client, db):
    """L'Italia alterna CET e CEST: a luglio lo stesso orario UTC va
    mostrato con due ore di scarto, non una."""
    utente = crea_studente(db)
    luglio = datetime(2026, 7, 15, 14, 30, tzinfo=timezone.utc).replace(tzinfo=None)
    slot = crea_slot(db, luglio, is_available=False)
    crea_prenotazione(db, utente, slot)

    risposta = client.get(
        "/users/me/prenotazioni",
        cookies=studente_cookies(utente.id, utente.email)
    )

    voce = risposta.json()[0]
    assert voce["ora"] == "16:30"   # CEST, UTC+2
    assert voce["start_time_iso"] == "2026-07-15T14:30:00+00:00"
