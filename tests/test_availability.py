# Copre backend/services/availability_service.py e la parte di
# backend/routers/admin/availability.py legata alle regole ricorrenti —
# finora senza nessun test dedicato. Vedi tests/conftest.py per come sono
# preparati client/db.

from datetime import datetime, time, timedelta

from backend.models.slots import Slot
from backend.models.users import User
from backend.models.booking import Booking
from backend.models.availability_rule import AvailabilityRule
from backend.services.availability_service import elimina_slot_obsoleti, genera_slot_da_regola
from conftest import admin_headers, crea_slot

FUTURO = datetime(2030, 1, 7, 15, 0, 0)
PASSATO = datetime(2020, 1, 7, 15, 0, 0)


def test_regola_con_durata_diversa_da_1_ora_viene_rifiutata(client, db):
    """
    Il calendario genera solo slot da 1 ora: le sessioni da 2h uniscono due
    slot da 1h adiacenti al momento della prenotazione (vedi
    ORE_INIZIO_VALIDE_2H in backend/routers/booking.py). Una regola con
    durata_slot_ore=2 genererebbe invece slot reali da 2h che bypassano
    quel vincolo di orario (15:00/17:00) — bloccato qui, non solo omesso
    dal form admin.
    """
    res = client.post(
        "/admin/disponibilita/regole",
        headers=admin_headers(),
        json={
            "giorno_settimana": 1,
            "ora_inizio": "18:00:00",
            "ora_fine": "22:00:00",
            "durata_slot_ore": 2
        }
    )
    assert res.status_code == 422


def test_regola_con_durata_1_ora_viene_accettata(client, db):
    res = client.post(
        "/admin/disponibilita/regole",
        headers=admin_headers(),
        json={
            "giorno_settimana": 1,
            "ora_inizio": "18:00:00",
            "ora_fine": "22:00:00",
            "durata_slot_ore": 1
        }
    )
    assert res.status_code == 200, res.text


def test_genera_slot_da_regola_ignora_regola_legacy_da_2_ore(db):
    """
    Difesa in profondità: AvailabilityRuleCreate rifiuta già durata_slot_ore
    diverso da 1 in scrittura (vedi il test sopra), ma una riga con
    durata_slot_ore=2 potrebbe comunque esistere nel database se creata
    prima che quel controllo esistesse (inserita qui direttamente, bypassando
    lo schema Pydantic, per simulare esattamente quel caso). Il job notturno
    genera_slot_giornaliero deve ignorarla, non continuare a generare slot
    da 2h prenotabili fuori dalla fascia 15:00/17:00.
    """
    regola_legacy = AvailabilityRule(
        giorno_settimana=datetime.today().weekday(),
        ora_inizio=time(18, 0),
        ora_fine=time(20, 0),
        durata_slot_ore=2,
        attiva=True,
    )
    db.add(regola_legacy)
    db.commit()
    db.refresh(regola_legacy)

    creati = genera_slot_da_regola(regola_legacy, db)

    assert creati == 0
    assert db.query(Slot).filter(Slot.duration_hours == 2).count() == 0


def test_elimina_slot_obsoleti_rimuove_slot_passato_mai_prenotato(db):
    slot = crea_slot(db, PASSATO)
    eliminati = elimina_slot_obsoleti(db)
    assert eliminati == 1
    assert db.query(Slot).filter(Slot.id == slot.id).first() is None


def test_elimina_slot_obsoleti_non_tocca_slot_futuri(db):
    slot = crea_slot(db, FUTURO)
    eliminati = elimina_slot_obsoleti(db)
    assert eliminati == 0
    assert db.query(Slot).filter(Slot.id == slot.id).first() is not None


def test_elimina_slot_obsoleti_preserva_slot_con_prenotazione_cancellata(db):
    """
    Uno slot passato con is_available=True può anche essere uno che ERA
    prenotato ed è stato poi cancellato (libera_slot_prenotazione lo riapre
    senza eliminare la riga Booking, che resta con status="cancelled") —
    va preservato per non perdere lo storico, esattamente come la
    cancellazione manuale (DELETE /admin/slots/{id}) già si rifiuta di
    eliminarlo.
    """
    slot = crea_slot(db, PASSATO, is_available=True)
    utente = User(nome="Test", email="storico@example.com")
    db.add(utente)
    db.commit()
    db.refresh(utente)

    prenotazione = Booking(
        user_id=utente.id, slot_id=slot.id, duration_hours=1,
        price_cents=2000, service_type="vod_review", status="cancelled"
    )
    db.add(prenotazione)
    db.commit()

    eliminati = elimina_slot_obsoleti(db)
    assert eliminati == 0
    assert db.query(Slot).filter(Slot.id == slot.id).first() is not None


def test_elimina_slot_obsoleti_rimuove_anche_slot_bloccato_mai_prenotato(db):
    """
    Uno slot passato bloccato (es. da un blocco eccezionale/ferie mai
    utilizzato) non ha nessun valore storico da preservare se nessuna
    prenotazione lo referenzia — va ripulito come uno slot libero.
    """
    slot = crea_slot(db, PASSATO, is_available=False)
    eliminati = elimina_slot_obsoleti(db)
    assert eliminati == 1
    assert db.query(Slot).filter(Slot.id == slot.id).first() is None


def test_elimina_slot_rifiuta_slot_secondario_di_una_sessione_da_2h(client, db):
    """
    Una sessione da 2h unisce due slot da 1h adiacenti: il primo tramite
    Booking.slot_id, il secondo tramite Booking.slot_id_secondario (vedi
    backend/models/booking.py). Cancellare lo slot referenziato SOLO come
    slot_id_secondario deve dare lo stesso 400 pulito dello slot
    referenziato come slot_id — non un errore del database, dato che
    entrambe le colonne sono una ForeignKey verso slots.id.
    """
    utente = User(nome="Test", email="due-ore@example.com")
    db.add(utente)
    db.commit()
    db.refresh(utente)

    slot_primario = crea_slot(db, datetime(2030, 1, 8, 14, 0, 0), is_available=False)
    slot_secondario = crea_slot(db, datetime(2030, 1, 8, 15, 0, 0), is_available=False)

    prenotazione = Booking(
        user_id=utente.id, slot_id=slot_primario.id, slot_id_secondario=slot_secondario.id,
        duration_hours=2, price_cents=4000, service_type="vod_review", status="confirmed"
    )
    db.add(prenotazione)
    db.commit()

    res = client.delete(f"/admin/slots/{slot_secondario.id}", headers=admin_headers())

    assert res.status_code == 400, res.text
    assert db.query(Slot).filter(Slot.id == slot_secondario.id).first() is not None
