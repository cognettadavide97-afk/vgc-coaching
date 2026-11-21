"""L'orario di una prenotazione si legge dalla prenotazione, non dallo slot (pezzo 4.3a, P9).

Ogni test costruisce una prenotazione il cui slot dice un orario e la
prenotazione un altro. Nella realtà i due coincidono sempre (create_booking
copia l'uno nell'altro), quindi la situazione è artificiale: è quella del
pezzo 4.4, in cui la prenotazione non avrà più uno slot. Se un punto del
codice risponde con l'orario dello slot, lo sta ancora leggendo da lì e
smetterà di funzionare quando gli slot spariranno.

Un test per ciascuno degli undici punti che leggono l'orario.
"""

import csv
import io
from datetime import datetime, time, timedelta, timezone

import backend.scheduler as scheduler_module
from backend.models.availability_rule import AvailabilityRule
from backend.models.booking import Booking
from backend.models.users import User
from backend.services import disponibilita_service
from backend.services.disponibilita_service import calcola_disponibilita
from backend.services.timezone_service import ROME_TZ, ora_utc_naive
from conftest import TestingSessionLocal, admin_headers, crea_slot, studente_cookies

# 16/07/2030, martedì d'estate: le 18:00 italiane sono le 16:00 UTC, le 15:00
# italiane le 13:00 UTC.
ORE_18_ROMA = datetime(2030, 7, 16, 16, 0)
ORE_15_ROMA = datetime(2030, 7, 16, 13, 0)


def utente_db(db):
    utente = User(nome="Cliente Test", email="cliente@example.com", categoria="senior")
    db.add(utente)
    db.commit()
    db.refresh(utente)
    return utente


def prenotazione_spostata(db, utente, ora_prenotazione, ora_slot, **campi):
    """Prenotazione con il proprio orario diverso da quello del suo slot."""
    slot = crea_slot(db, ora_slot, is_available=False)
    prenotazione = Booking(
        user_id=utente.id, slot_id=slot.id, start_time=ora_prenotazione,
        duration_hours=1, price_cents=campi.get("price_cents", 2000),
        service_type="vod_review", status=campi.get("status", "confirmed"),
        review_token=campi.get("review_token"),
    )
    db.add(prenotazione)
    db.commit()
    db.refresh(prenotazione)
    return prenotazione


# ─── routers/booking.py ───────────────────────────────────────

def test_il_limite_di_prenotazioni_attive_guarda_l_orario_della_prenotazione(client, db):
    utente = utente_db(db)
    adesso = ora_utc_naive()
    # Due prenotazioni future con lo slot nel passato: sono attive.
    for giorni in (3, 4):
        prenotazione_spostata(db, utente, adesso + timedelta(days=giorni), adesso - timedelta(days=giorni))
    slot = crea_slot(db, adesso + timedelta(days=5))

    res = client.post("/bookings/", json={
        "user_id": utente.id, "email": utente.email, "slot_id": slot.id,
        "duration_hours": 1, "service_type": "vod_review"
    })

    assert res.status_code == 400, res.text
    assert "active bookings" in res.json()["detail"]


def test_la_cancellazione_del_cliente_guarda_l_orario_della_prenotazione(client, db):
    utente = utente_db(db)
    adesso = ora_utc_naive()
    # Sessione futura con lo slot nel passato: si può ancora cancellare.
    prenotazione = prenotazione_spostata(db, utente, adesso + timedelta(days=3), adesso - timedelta(days=3))

    res = client.patch(
        f"/bookings/{prenotazione.id}/cancella",
        cookies=studente_cookies(utente.id, utente.email)
    )

    assert res.status_code == 200, res.text


# ─── pannello: lista, CSV, dashboard, analytics ───────────────

def test_la_lista_del_pannello_mostra_l_orario_della_prenotazione(client, db):
    prenotazione_spostata(db, utente_db(db), ORE_18_ROMA, ORE_15_ROMA)

    res = client.get("/admin/prenotazioni", headers=admin_headers())

    assert res.status_code == 200, res.text
    assert res.json()["items"][0]["slot"] == {"data": "16/07/2030", "ora": "18:00"}


def test_l_export_csv_riporta_l_orario_della_prenotazione(client, db):
    prenotazione_spostata(db, utente_db(db), ORE_18_ROMA, ORE_15_ROMA)

    res = client.get("/admin/export/csv", headers=admin_headers())

    assert res.status_code == 200, res.text
    righe = list(csv.reader(io.StringIO(res.content.decode("utf-8-sig"))))
    intestazione, riga = righe[0], righe[1]
    assert riga[intestazione.index("Data")] == "16/07/2030"
    assert riga[intestazione.index("Ora")] == "18:00"


def test_la_dashboard_conta_oggi_la_prenotazione_di_oggi(client, db):
    # Mezzogiorno di oggi a Roma: è "oggi" a qualunque ora giri il test.
    mezzogiorno_roma = datetime.now(timezone.utc).astimezone(ROME_TZ).replace(
        hour=12, minute=0, second=0, microsecond=0
    )
    oggi = mezzogiorno_roma.astimezone(timezone.utc).replace(tzinfo=None)
    prenotazione_spostata(db, utente_db(db), oggi, oggi + timedelta(days=10))

    dati = client.get("/admin/dashboard", headers=admin_headers()).json()

    assert dati["prenotazioni_oggi"] == 1


def test_le_analytics_contano_la_sessione_nel_mese_della_prenotazione(client, db):
    adesso = ora_utc_naive()
    # Prenotazione di 10 giorni fa, slot di 400 giorni fa: fuori dalla
    # finestra di 12 mesi solo se si guarda lo slot.
    prenotazione_spostata(db, utente_db(db), adesso - timedelta(days=10), adesso - timedelta(days=400))

    dati = client.get("/admin/analytics", headers=admin_headers()).json()

    assert sum(m["conteggio"] for m in dati["sessioni_per_mese"]) == 1


def test_l_incasso_conta_la_sessione_svolta_secondo_la_prenotazione(client, db):
    adesso = ora_utc_naive()
    # Sessione di due giorni fa, slot futuro: è svolta, quindi incassata.
    prenotazione_spostata(db, utente_db(db), adesso - timedelta(days=2), adesso + timedelta(days=2))

    dati = client.get("/admin/dashboard", headers=admin_headers()).json()

    assert dati["totale_incassato_euro"] == 20.0


# ─── studente ─────────────────────────────────────────────────

def test_lo_storico_dello_studente_mostra_l_orario_della_prenotazione(client, db):
    utente = utente_db(db)
    prenotazione_spostata(db, utente, ORE_18_ROMA, ORE_15_ROMA)

    res = client.get("/users/me/prenotazioni", cookies=studente_cookies(utente.id, utente.email))

    assert res.status_code == 200, res.text
    voce = res.json()[0]
    assert voce["ora"] == "18:00"
    assert voce["start_time_iso"] == "2030-07-16T16:00:00+00:00"


# ─── job: promemoria e recensioni ─────────────────────────────

def test_il_promemoria_parte_secondo_l_orario_della_prenotazione(db, monkeypatch):
    monkeypatch.setattr(scheduler_module, "SessionLocal", TestingSessionLocal)
    inviati = []
    monkeypatch.setattr(scheduler_module, "invia_promemoria_cliente", lambda **kw: inviati.append(kw) or True)
    monkeypatch.setattr(scheduler_module, "invia_promemoria_discord", lambda **kw: None)
    adesso = ora_utc_naive().replace(second=0, microsecond=0)
    # Sessione fra 2 ore (dentro le 24 del promemoria), slot fra 10 giorni.
    inizio = adesso + timedelta(hours=2)
    prenotazione_spostata(db, utente_db(db), inizio, adesso + timedelta(days=10))

    assert scheduler_module.controlla_e_invia_promemoria() == 1
    ora_roma = inizio.replace(tzinfo=timezone.utc).astimezone(ROME_TZ)
    assert inviati[0]["ora_slot"] == ora_roma.strftime("%H:%M")


def test_la_richiesta_di_recensione_parte_secondo_l_orario_della_prenotazione(db, monkeypatch):
    monkeypatch.setattr(scheduler_module, "SessionLocal", TestingSessionLocal)
    inviate = []
    monkeypatch.setattr(scheduler_module, "invia_richiesta_recensione", lambda **kw: inviate.append(kw) or True)
    adesso = ora_utc_naive()
    # Sessione di 3 ore fa (conclusa), slot fra 10 giorni.
    prenotazione_spostata(db, utente_db(db), adesso - timedelta(hours=3), adesso + timedelta(days=10),
                          review_token="token-di-prova")

    assert scheduler_module.controlla_e_invia_richieste_recensione() == 1
    assert len(inviate) == 1


# ─── calcolo della disponibilità (4.2) ────────────────────────

def test_il_calcolo_toglie_l_ora_della_prenotazione(db, monkeypatch):
    monkeypatch.setattr(disponibilita_service, "leggi_eventi_calendario", lambda da, a: [])
    # Regola del martedì 15-19; la prenotazione occupa le 15, il suo slot è
    # una settimana dopo.
    db.add(AvailabilityRule(giorno_settimana=1, ora_inizio=time(15), ora_fine=time(19), durata_slot_ore=1))
    db.commit()
    prenotazione_spostata(db, utente_db(db), ORE_15_ROMA, ORE_15_ROMA + timedelta(days=7))

    libere = calcola_disponibilita(db, datetime(2030, 7, 16), datetime(2030, 7, 17))

    assert ORE_15_ROMA not in libere[1]
