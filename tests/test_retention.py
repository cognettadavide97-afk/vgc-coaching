# Copre anonimizza_clienti_inattivi (backend/services/retention_service.py),
# il job di data retention che gira ogni notte da backend/scheduler.py
# (controlla_e_anonimizza_clienti_inattivi). I model vengono creati
# direttamente sul database di test (non via API) per poter controllare a
# mano le date "created_at", altrimenti sempre valorizzate da func.now()
# al momento vero dell'inserimento — vedi tests/conftest.py per come sono
# preparati client/db.

from datetime import datetime, timedelta, timezone

from backend.models.users import User
from backend.models.slots import Slot
from backend.models.booking import Booking
from backend.models.package import Package
from backend.services.retention_service import anonimizza_clienti_inattivi, SUFFISSO_EMAIL_ANONIMIZZATA

ORA = datetime.now(timezone.utc).replace(tzinfo=None)
VECCHIO = ORA - timedelta(days=800)   # oltre 24 mesi fa
RECENTE = ORA - timedelta(days=10)


def crea_utente_db(db, created_at, email="cliente@example.com", anonimizzato_at=None):
    utente = User(
        nome="Cliente Test",
        email=email,
        telefono="333123456",
        discord_tag="clientetest",
        discord_id="123456789",
        created_at=created_at,
        anonimizzato_at=anonimizzato_at
    )
    db.add(utente)
    db.commit()
    db.refresh(utente)
    return utente


def test_anonimizza_cliente_inattivo_da_piu_di_24_mesi(db):
    utente = crea_utente_db(db, created_at=VECCHIO)

    anonimizzati = anonimizza_clienti_inattivi(db)

    assert anonimizzati == 1
    db.refresh(utente)
    assert utente.nome == "Cliente anonimizzato"
    assert utente.email.endswith(SUFFISSO_EMAIL_ANONIMIZZATA)
    assert utente.telefono is None
    assert utente.discord_tag is None
    assert utente.discord_id is None
    assert utente.anonimizzato_at is not None


def test_non_anonimizza_cliente_con_prenotazione_recente(db):
    # Cliente registrato oltre 24 mesi fa, ma con una prenotazione recente:
    # l'ultima attività vince sulla data di registrazione, quindi non deve
    # essere toccato.
    utente = crea_utente_db(db, created_at=VECCHIO)

    slot = Slot(start_time=ORA + timedelta(days=5), duration_hours=1, is_available=False)
    db.add(slot)
    db.commit()
    db.refresh(slot)

    prenotazione = Booking(
        user_id=utente.id,
        slot_id=slot.id,
        duration_hours=1,
        price_cents=2000,
        service_type="vod_review",
        created_at=RECENTE
    )
    db.add(prenotazione)
    db.commit()

    anonimizzati = anonimizza_clienti_inattivi(db)

    assert anonimizzati == 0
    db.refresh(utente)
    assert utente.nome == "Cliente Test"
    assert utente.email == "cliente@example.com"


def test_non_anonimizza_cliente_con_pacchetto_recente(db):
    utente = crea_utente_db(db, created_at=VECCHIO)

    pacchetto = Package(
        user_id=utente.id,
        tipo="intro",
        sessioni_totali=2,
        prezzo_cents=7000,
        created_at=RECENTE
    )
    db.add(pacchetto)
    db.commit()

    anonimizzati = anonimizza_clienti_inattivi(db)

    assert anonimizzati == 0
    db.refresh(utente)
    assert utente.email == "cliente@example.com"


def test_non_ri_anonimizza_un_cliente_gia_anonimizzato(db):
    # "Già anonimizzato" si riconosce da anonimizzato_at valorizzata (una
    # colonna vera), non più da una convenzione sul formato dell'email.
    crea_utente_db(
        db, created_at=VECCHIO,
        email=f"anonimizzato-1{SUFFISSO_EMAIL_ANONIMIZZATA}",
        anonimizzato_at=VECCHIO
    )

    anonimizzati = anonimizza_clienti_inattivi(db)

    assert anonimizzati == 0
