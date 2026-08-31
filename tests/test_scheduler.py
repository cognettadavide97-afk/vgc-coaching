# Copre i job periodici di backend/scheduler.py che girano da soli in
# produzione, senza che nessuna richiesta HTTP li attivi (vedi il commento
# in cima a quel file). Non usano Depends(get_db): aprono da soli una
# connessione con SessionLocal(), che di default punta al DATABASE_URL
# reale configurato in .env — non al database SQLite isolato che il resto
# della suite usa tramite l'override di get_db (vedi tests/conftest.py).
#
# Senza il monkeypatch esplicito qui sotto, chiamare queste funzioni
# scriverebbe (e leggerebbe) sul database di sviluppo VERO — è già successo
# per errore in questo progetto in passato, mandando anche email/messaggi
# Discord reali con le credenziali vere di .env (le stesse funzioni di invio
# vengono comunque mockate qui sotto, in aggiunta, per sicurezza doppia).

from datetime import timedelta

import backend.scheduler as scheduler_module
from backend.models.users import User
from backend.models.booking import Booking
from conftest import crea_slot, TestingSessionLocal


def finge_sessione_scheduler(monkeypatch):
    """
    Fa sì che backend/scheduler.py, quando apre SessionLocal() da solo,
    usi lo stesso database SQLite isolato del resto della suite invece del
    DATABASE_URL reale — vedi il commento in cima al file.
    """
    monkeypatch.setattr(scheduler_module, "SessionLocal", TestingSessionLocal)


def crea_utente_db(db, email="cliente@example.com", nome="Cliente Test"):
    utente = User(nome=nome, email=email)
    db.add(utente)
    db.commit()
    db.refresh(utente)
    return utente


def crea_prenotazione_db(db, utente, slot, **campi):
    prenotazione = Booking(
        user_id=utente.id, slot_id=slot.id,
        duration_hours=campi.get("duration_hours", 1),
        price_cents=campi.get("price_cents", 2000),
        service_type=campi.get("service_type", "vod_review"),
        status=campi.get("status", "confirmed"),
        reminder_sent=campi.get("reminder_sent", False),
        review_email_sent=campi.get("review_email_sent", False),
        review_token=campi.get("review_token"),
    )
    db.add(prenotazione)
    db.commit()
    db.refresh(prenotazione)
    return prenotazione


# ─── controlla_e_invia_promemoria ─────────────────────────────

def test_promemoria_inviato_per_prenotazione_nella_finestra(db, monkeypatch):
    finge_sessione_scheduler(monkeypatch)
    inviati_email = []
    inviati_discord = []
    monkeypatch.setattr(scheduler_module, "invia_promemoria_cliente", lambda **kw: inviati_email.append(kw))
    monkeypatch.setattr(scheduler_module, "invia_promemoria_discord", lambda **kw: inviati_discord.append(kw))

    utente = crea_utente_db(db)
    # REMINDER_HOURS_BEFORE di default è 24h — uno slot tra 2 ore è
    # abbastanza vicino da meritare il promemoria.
    slot = crea_slot(db, scheduler_module.ora_utc_naive() + timedelta(hours=2))
    prenotazione = crea_prenotazione_db(db, utente, slot)

    risultato = scheduler_module.controlla_e_invia_promemoria()

    assert risultato == 1
    assert len(inviati_email) == 1
    assert len(inviati_discord) == 1
    db.refresh(prenotazione)
    assert prenotazione.reminder_sent is True


def test_promemoria_non_inviato_fuori_finestra(db, monkeypatch):
    finge_sessione_scheduler(monkeypatch)
    inviati = []
    monkeypatch.setattr(scheduler_module, "invia_promemoria_cliente", lambda **kw: inviati.append(kw))
    monkeypatch.setattr(scheduler_module, "invia_promemoria_discord", lambda **kw: None)

    utente = crea_utente_db(db)
    # Ben oltre REMINDER_HOURS_BEFORE (24h di default): non ancora "vicino".
    slot = crea_slot(db, scheduler_module.ora_utc_naive() + timedelta(days=10))
    prenotazione = crea_prenotazione_db(db, utente, slot)

    risultato = scheduler_module.controlla_e_invia_promemoria()

    assert risultato == 0
    assert inviati == []
    db.refresh(prenotazione)
    assert prenotazione.reminder_sent is False


def test_promemoria_gia_inviato_non_si_ripete(db, monkeypatch):
    finge_sessione_scheduler(monkeypatch)
    inviati = []
    monkeypatch.setattr(scheduler_module, "invia_promemoria_cliente", lambda **kw: inviati.append(kw))
    monkeypatch.setattr(scheduler_module, "invia_promemoria_discord", lambda **kw: None)

    utente = crea_utente_db(db)
    slot = crea_slot(db, scheduler_module.ora_utc_naive() + timedelta(hours=2))
    crea_prenotazione_db(db, utente, slot, reminder_sent=True)

    risultato = scheduler_module.controlla_e_invia_promemoria()

    assert risultato == 0
    assert inviati == []
