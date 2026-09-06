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


# ─── controlla_credenziali ────────────────────────────────────
#
# Questo job non manda email e non fa backup: decide **quando avvisare e
# quando tacere** su Gmail, Drive e Calendar. Ha due modi opposti di
# rompersi, e nessuno dei due si nota subito: un alert che non parte quando
# una credenziale muore (l'invio email è fermo e nessuno lo sa), o un alert
# ripetuto a ogni esecuzione, che si impara a ignorare. È lo stesso punto
# che nel settembre 2026 aveva già suonato falso per una sonda sbagliata,
# quindi qui si controllano tutte le combinazioni stato-precedente/attuale.
#
# Lo stato precedente vive in un dizionario di modulo che sopravvive fra un
# test e l'altro: ogni test lo azzera con monkeypatch, che lo ripristina da
# solo alla fine.


def credenziale_finta(esito, nome="Prova"):
    """Una CredenzialeSorvegliata la cui sonda restituisce `esito`."""
    return scheduler_module.CredenzialeSorvegliata(
        nome=nome,
        sonda=lambda: esito,
        cosa_si_ferma="Qualcosa si è fermato.",
        come_si_ripara="Rifai l'autorizzazione.",
    )


def prepara_controllo(monkeypatch, stato_precedente, nome="Prova"):
    """Imposta lo stato ricordato dall'esecuzione precedente e raccoglie gli
    alert Discord invece di inviarli."""
    stato = {} if stato_precedente is None else {nome: stato_precedente}
    monkeypatch.setattr(scheduler_module, "_ultimo_controllo_credenziali", stato)
    alert = []
    monkeypatch.setattr(
        scheduler_module, "invia_alert_sistema",
        lambda titolo, descrizione: alert.append((titolo, descrizione))
    )
    return alert


def test_primo_controllo_con_credenziale_valida_non_avvisa(monkeypatch):
    # Stato assente = mai controllata in questo processo (appena riavviato).
    alert = prepara_controllo(monkeypatch, stato_precedente=None)

    risultato = scheduler_module.controlla_una_credenziale(credenziale_finta(True))

    assert risultato is True
    assert alert == []
    assert scheduler_module._ultimo_controllo_credenziali["Prova"] is True


def test_primo_controllo_con_credenziale_rotta_avvisa(monkeypatch):
    """Al primo controllo dopo un riavvio lo stato precedente è assente, non
    False: l'alert deve partire lo stesso, altrimenti un processo riavviato
    con la credenziale già morta resterebbe muto per sempre."""
    alert = prepara_controllo(monkeypatch, stato_precedente=None)

    risultato = scheduler_module.controlla_una_credenziale(credenziale_finta(False))

    assert risultato is False
    assert len(alert) == 1
    titolo, descrizione = alert[0]
    assert "Prova" in titolo and "non valide" in titolo
    # L'alert deve dire cosa si è fermato e cosa fare, non solo che è rotto.
    assert "Qualcosa si è fermato." in descrizione
    assert "Rifai l'autorizzazione." in descrizione


def test_transizione_da_valida_a_rotta_avvisa(monkeypatch):
    alert = prepara_controllo(monkeypatch, stato_precedente=True)

    scheduler_module.controlla_una_credenziale(credenziale_finta(False))

    assert len(alert) == 1
    assert "non valide" in alert[0][0]


def test_problema_persistente_non_ripete_l_alert(monkeypatch):
    """La credenziale è rotta ed era già rotta al controllo precedente:
    silenzio. È il motivo per cui esiste il dizionario di stato."""
    alert = prepara_controllo(monkeypatch, stato_precedente=False)

    risultato = scheduler_module.controlla_una_credenziale(credenziale_finta(False))

    assert risultato is False
    assert alert == []
    assert scheduler_module._ultimo_controllo_credenziali["Prova"] is False


def test_ritorno_alla_normalita_avvisa(monkeypatch):
    """Anche il rientro va notificato: senza, chi ha rifatto
    l'autorizzazione non sa dal monitoraggio se ha funzionato."""
    alert = prepara_controllo(monkeypatch, stato_precedente=False)

    risultato = scheduler_module.controlla_una_credenziale(credenziale_finta(True))

    assert risultato is True
    assert len(alert) == 1
    assert "di nuovo valide" in alert[0][0]
    assert scheduler_module._ultimo_controllo_credenziali["Prova"] is True


def test_tutto_a_posto_non_avvisa(monkeypatch):
    alert = prepara_controllo(monkeypatch, stato_precedente=True)

    scheduler_module.controlla_una_credenziale(credenziale_finta(True))

    assert alert == []


# --- Le tre credenziali insieme -------------------------------

def test_ogni_credenziale_ha_uno_stato_indipendente(monkeypatch):
    """Il punto della generalizzazione: se lo stato fosse condiviso, Drive
    rotto dopo Gmail rotto passerebbe per "nessun cambiamento" e non
    verrebbe segnalato."""
    alert = prepara_controllo(monkeypatch, stato_precedente=None)

    scheduler_module.controlla_una_credenziale(credenziale_finta(False, nome="Gmail"))
    scheduler_module.controlla_una_credenziale(credenziale_finta(False, nome="Drive"))

    assert len(alert) == 2
    assert "Gmail" in alert[0][0]
    assert "Drive" in alert[1][0]


def test_controlla_credenziali_le_sonda_tutte_e_tre(monkeypatch):
    """Che il job giri davvero su tutte e tre, e non su una sola: una sonda
    dimenticata nella lista non farebbe fallire nessun altro test."""
    monkeypatch.setattr(scheduler_module, "_ultimo_controllo_credenziali", {})
    monkeypatch.setattr(scheduler_module, "invia_alert_sistema", lambda t, d: None)
    monkeypatch.setattr(
        scheduler_module, "CREDENZIALI_SORVEGLIATE",
        tuple(credenziale_finta(True, nome=n) for n in ("Gmail", "Drive", "Calendar"))
    )

    esiti = scheduler_module.controlla_credenziali()

    assert esiti == {"Gmail": True, "Drive": True, "Calendar": True}


def test_la_lista_reale_sorveglia_le_tre_integrazioni_google():
    """Controlla la configurazione vera, non una finta: le tre integrazioni
    Google devono essere tutte sotto sorveglianza, ciascuna con la propria
    sonda e con un testo di riparazione non vuoto."""
    per_nome = {c.nome: c for c in scheduler_module.CREDENZIALI_SORVEGLIATE}

    assert set(per_nome) == {"Gmail", "Drive", "Calendar"}
    assert per_nome["Gmail"].sonda is scheduler_module.verifica_credenziali_gmail
    assert per_nome["Drive"].sonda is scheduler_module.verifica_credenziali_drive
    assert per_nome["Calendar"].sonda is scheduler_module.verifica_credenziali_calendario
    for credenziale in per_nome.values():
        assert credenziale.cosa_si_ferma and credenziale.come_si_ripara


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


# ─── Cadenza dei job ──────────────────────────────────────────
#
# La collocazione oraria di questi due job non è un dettaglio di comodo: è
# ciò che rende utile la sonda Drive. Controllare le credenziali DOPO il
# backup significherebbe scoprire il token morto a copia già saltata, cioè
# esattamente il difetto che la sonda esiste per eliminare. Un riordino
# fatto in buona fede, o uno dei due job spostato senza l'altro, non
# romperebbe nessun altro test: per questo l'ordine è fissato qui.

def leggi_job_registrati(monkeypatch):
    """Registra i job su uno scheduler finto invece di avviarne uno vero.

    Un BackgroundScheduler vero farebbe partire un thread che, a orario,
    eseguirebbe i job contro il database e i servizi esterni reali.
    """
    registrati = {}

    class SchedulerFinto:
        def add_job(self, funzione, trigger, **opzioni):
            registrati[opzioni["id"]] = (funzione, trigger, opzioni)

        def start(self):
            pass

    monkeypatch.setattr(scheduler_module, "BackgroundScheduler", SchedulerFinto)
    scheduler_module.avvia_scheduler()
    return registrati


def test_credenziali_e_backup_girano_una_volta_a_settimana(monkeypatch):
    job = leggi_job_registrati(monkeypatch)

    for id_job in ("controlla_credenziali", "backup_database"):
        _, trigger, opzioni = job[id_job]
        assert trigger == "cron", f"{id_job} deve avere un orario fisso, non un intervallo"
        assert opzioni["day_of_week"] == "sun", f"{id_job} deve girare la domenica"


def test_le_credenziali_si_controllano_prima_del_backup(monkeypatch):
    """Mezz'ora prima, così un token Drive morto viene segnalato PRIMA che
    la copia salti — invece che dopo, come succedeva senza la sonda."""
    job = leggi_job_registrati(monkeypatch)

    _, _, credenziali = job["controlla_credenziali"]
    _, _, backup = job["backup_database"]

    minuti_credenziali = credenziali["hour"] * 60 + credenziali["minute"]
    minuti_backup = backup["hour"] * 60 + backup["minute"]

    assert minuti_credenziali < minuti_backup
    assert minuti_backup - minuti_credenziali == 30


def test_gli_altri_job_notturni_restano_giornalieri(monkeypatch):
    """Solo credenziali e backup passano a settimanale: generazione slot,
    retention e pulizia restano quotidiane, e la pulizia deve continuare a
    precedere il backup."""
    job = leggi_job_registrati(monkeypatch)

    for id_job in ("genera_slot_giornaliero", "controlla_retention_clienti", "pulisci_slot_obsoleti"):
        _, trigger, opzioni = job[id_job]
        assert trigger == "cron"
        assert "day_of_week" not in opzioni, f"{id_job} non deve essere settimanale"

    _, _, pulizia = job["pulisci_slot_obsoleti"]
    _, _, backup = job["backup_database"]
    assert pulizia["hour"] * 60 + pulizia["minute"] < backup["hour"] * 60 + backup["minute"]
