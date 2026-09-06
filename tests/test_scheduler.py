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


# ─── controlla_e_invia_richieste_recensione ───────────────────

def test_richiesta_recensione_inviata_per_sessione_conclusa(db, monkeypatch):
    finge_sessione_scheduler(monkeypatch)
    inviate = []
    monkeypatch.setattr(scheduler_module, "invia_richiesta_recensione", lambda **kw: inviate.append(kw))

    utente = crea_utente_db(db)
    # Slot iniziato 3 ore fa, durata 1h di default: la sessione è conclusa
    # da 2 ore, oltre il pre-filtro largo della funzione.
    slot = crea_slot(db, scheduler_module.ora_utc_naive() - timedelta(hours=3), is_available=False)
    prenotazione = crea_prenotazione_db(db, utente, slot, review_token="token-test-123")

    risultato = scheduler_module.controlla_e_invia_richieste_recensione()

    assert risultato == 1
    assert len(inviate) == 1
    db.refresh(prenotazione)
    assert prenotazione.review_email_sent is True


def test_richiesta_recensione_non_inviata_se_sessione_non_ancora_conclusa(db, monkeypatch):
    finge_sessione_scheduler(monkeypatch)
    inviate = []
    monkeypatch.setattr(scheduler_module, "invia_richiesta_recensione", lambda **kw: inviate.append(kw))

    utente = crea_utente_db(db)
    # Pre-filtro largo (backend/scheduler.py): "nessuna sessione dura più di
    # 2 ore" è vero solo per le prenotazioni create dal flusso normale
    # (TABELLA_PREZZI in backend/routers/booking.py ammette solo 1h/2h) — il
    # controllo Python esatto sotto è una rete di sicurezza per quando
    # quell'assunzione non vale (qui: duration_hours=3, scritta direttamente
    # sul DB di test, non ottenibile dal flusso di prenotazione normale).
    # Con lo slot iniziato 2h10' fa il pre-filtro SQL la include comunque,
    # ma con 3 ore di durata la sessione finisce solo tra 50 minuti.
    slot = crea_slot(db, scheduler_module.ora_utc_naive() - timedelta(hours=2, minutes=10), is_available=False)
    prenotazione = crea_prenotazione_db(db, utente, slot, duration_hours=3, review_token="token-test-456")

    risultato = scheduler_module.controlla_e_invia_richieste_recensione()

    assert risultato == 0
    assert inviate == []
    db.refresh(prenotazione)
    assert prenotazione.review_email_sent is False


# ─── controlla_credenziali_gmail ──────────────────────────────
#
# Questo job non manda email: decide quando *avvisare* che l'invio email è
# fermo. Avvisa solo alla transizione fra valido e non valido, per non
# ripetere lo stesso alert ogni 24 ore mentre il problema persiste — il che
# significa che due difetti opposti sono possibili e nessuno dei due si
# nota subito: un alert che non parte quando il token muore (l'invio email
# è fermo e nessuno lo sa), o un alert ripetuto all'infinito che si impara
# a ignorare. È lo stesso meccanismo che nel settembre 2026 ha suonato
# falso per una sonda sbagliata, quindi qui si controllano tutte e quattro
# le combinazioni stato-precedente/stato-attuale.
#
# Lo stato precedente vive in una variabile globale del modulo, che
# sopravvive fra un test e l'altro: ogni test la riporta al valore di
# partenza che gli serve con monkeypatch, che la ripristina da solo a fine
# test.

def prepara_controllo_gmail(monkeypatch, stato_precedente, token_valido):
    """Imposta lo stato ricordato dall'esecuzione precedente e l'esito del
    prossimo controllo, e raccoglie gli alert Discord invece di inviarli."""
    monkeypatch.setattr(scheduler_module, "_ultimo_controllo_gmail_ok", stato_precedente)
    monkeypatch.setattr(scheduler_module, "verifica_credenziali_gmail", lambda: token_valido)
    alert = []
    monkeypatch.setattr(
        scheduler_module, "invia_alert_sistema",
        lambda titolo, descrizione: alert.append((titolo, descrizione))
    )
    return alert


def test_gmail_primo_controllo_con_token_valido_non_avvisa(monkeypatch):
    # None = mai controllato in questo processo (appena riavviato).
    alert = prepara_controllo_gmail(monkeypatch, stato_precedente=None, token_valido=True)

    risultato = scheduler_module.controlla_credenziali_gmail()

    assert risultato is True
    assert alert == []
    assert scheduler_module._ultimo_controllo_gmail_ok is True


def test_gmail_primo_controllo_con_token_rotto_avvisa(monkeypatch):
    """Al primo controllo dopo un riavvio lo stato precedente è None, non
    False: l'alert deve partire lo stesso, altrimenti un processo riavviato
    con il token già morto resterebbe muto per sempre."""
    alert = prepara_controllo_gmail(monkeypatch, stato_precedente=None, token_valido=False)

    risultato = scheduler_module.controlla_credenziali_gmail()

    assert risultato is False
    assert len(alert) == 1
    titolo, descrizione = alert[0]
    assert "scaduto o non valido" in titolo
    # L'alert deve dire cosa fare, non solo che qualcosa è rotto.
    assert "reauth_gmail.py" in descrizione
    assert scheduler_module._ultimo_controllo_gmail_ok is False


def test_gmail_transizione_da_valido_a_rotto_avvisa(monkeypatch):
    alert = prepara_controllo_gmail(monkeypatch, stato_precedente=True, token_valido=False)

    scheduler_module.controlla_credenziali_gmail()

    assert len(alert) == 1
    assert "scaduto o non valido" in alert[0][0]


def test_gmail_problema_persistente_non_ripete_l_alert(monkeypatch):
    """Il token è rotto ed era già rotto al controllo precedente: silenzio.
    È il motivo per cui esiste la variabile di stato."""
    alert = prepara_controllo_gmail(monkeypatch, stato_precedente=False, token_valido=False)

    risultato = scheduler_module.controlla_credenziali_gmail()

    assert risultato is False
    assert alert == []
    assert scheduler_module._ultimo_controllo_gmail_ok is False


def test_gmail_ritorno_alla_normalita_avvisa(monkeypatch):
    """Anche il rientro va notificato: senza, chi ha rifatto
    l'autorizzazione non sa dal monitoraggio se ha funzionato."""
    alert = prepara_controllo_gmail(monkeypatch, stato_precedente=False, token_valido=True)

    risultato = scheduler_module.controlla_credenziali_gmail()

    assert risultato is True
    assert len(alert) == 1
    assert "di nuovo valido" in alert[0][0]
    assert scheduler_module._ultimo_controllo_gmail_ok is True


def test_gmail_tutto_a_posto_non_avvisa(monkeypatch):
    alert = prepara_controllo_gmail(monkeypatch, stato_precedente=True, token_valido=True)

    scheduler_module.controlla_credenziali_gmail()

    assert alert == []


# ─── controlla_e_anonimizza_clienti_inattivi ──────────────────
#
# Il servizio sotto (anonimizza_clienti_inattivi) è già coperto al 100% da
# tests/test_retention.py: qui si copre il job che lo invoca, cioè due cose
# che quel servizio non decide — quando notificare, e cosa può contenere la
# notifica. Il secondo punto non è un dettaglio: scrivere nome o email del
# cliente nell'alert Discord rimetterebbe in circolo esattamente i dati
# appena rimossi dal database, vanificando l'anonimizzazione.

def crea_utente_inattivo(db, email, nome, giorni_fa=800):
    """Cliente la cui unica attività è la registrazione, abbastanza indietro
    da superare la soglia di retention (24 mesi di default)."""
    utente = User(
        nome=nome, email=email,
        created_at=scheduler_module.ora_utc_naive() - timedelta(days=giorni_fa)
    )
    db.add(utente)
    db.commit()
    db.refresh(utente)
    return utente


def test_anonimizzazione_senza_clienti_da_trattare_non_notifica(db, monkeypatch):
    finge_sessione_scheduler(monkeypatch)
    alert = []
    monkeypatch.setattr(scheduler_module, "invia_alert_sistema", lambda t, d: alert.append((t, d)))

    crea_utente_inattivo(db, "recente@example.com", "Cliente Recente", giorni_fa=10)

    anonimizzati = scheduler_module.controlla_e_anonimizza_clienti_inattivi()

    assert anonimizzati == 0
    assert alert == []


def test_anonimizzazione_notifica_solo_il_conteggio(db, monkeypatch):
    finge_sessione_scheduler(monkeypatch)
    alert = []
    monkeypatch.setattr(scheduler_module, "invia_alert_sistema", lambda t, d: alert.append((t, d)))

    crea_utente_inattivo(db, "mario.rossi@example.com", "Mario Rossi")
    crea_utente_inattivo(db, "luigi.verdi@example.com", "Luigi Verdi")

    anonimizzati = scheduler_module.controlla_e_anonimizza_clienti_inattivi()

    assert anonimizzati == 2
    assert len(alert) == 1
    titolo, descrizione = alert[0]
    assert "clienti anonimizzati" in titolo
    assert "2 cliente/i" in descrizione
    # Il punto del test: i dati appena rimossi non devono ricomparire qui.
    for dato_personale in ("Mario Rossi", "mario.rossi@example.com",
                           "Luigi Verdi", "luigi.verdi@example.com"):
        assert dato_personale not in descrizione


def test_anonimizzazione_scrive_davvero_sul_database(db, monkeypatch):
    """Il job restituisce un conteggio, ma quel che conta è l'effetto: il
    commit avviene dentro il servizio, su una sessione che il job chiude
    subito dopo — se non fosse committato, il conteggio sarebbe comunque 1."""
    finge_sessione_scheduler(monkeypatch)
    monkeypatch.setattr(scheduler_module, "invia_alert_sistema", lambda t, d: None)

    utente = crea_utente_inattivo(db, "mario.rossi@example.com", "Mario Rossi")

    scheduler_module.controlla_e_anonimizza_clienti_inattivi()

    db.refresh(utente)
    assert utente.nome == "Cliente anonimizzato"
    assert utente.email != "mario.rossi@example.com"
    assert utente.anonimizzato_at is not None
