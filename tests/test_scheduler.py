# Copre i job periodici di backend/scheduler.py che girano da soli in
# produzione, senza che nessuna richiesta HTTP li attivi (vedi il commento
# in cima a quel file). Non usano Depends(get_db): aprono da soli una
# connessione con SessionLocal(), che non è il database SQLite condiviso dal
# resto della suite tramite l'override di get_db (vedi tests/conftest.py).
#
# Fino alla voce 51 SessionLocal puntava al DATABASE_URL reale del .env, e
# chiamare queste funzioni senza il monkeypatch qui sotto scriveva sul
# database di sviluppo VERO — è successo per errore in passato, mandando
# anche email/messaggi Discord reali. Oggi conftest.py punta DATABASE_URL a
# un SQLite in memoria e blocca la rete, ma quel database è un altro: il
# monkeypatch serve perché job e test vedano gli stessi dati. Le funzioni di
# invio si sostituiscono per osservarle; quelle "riuscite" restituiscono
# True, perché il job segna come inviato solo ciò che è partito.

import threading
from datetime import datetime, timedelta, timezone

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobExecutionEvent
from apscheduler.schedulers.background import BackgroundScheduler

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
        user_id=utente.id, slot_id=slot.id, start_time=slot.start_time,
        duration_hours=campi.get("duration_hours", 1),
        price_cents=campi.get("price_cents", 2000),
        service_type=campi.get("service_type", "vod_review"),
        status=campi.get("status", "confirmed"),
        reminder_sent=campi.get("reminder_sent", False),
        review_email_sent=campi.get("review_email_sent", False),
        review_token=campi.get("review_token"),
        note_cliente=campi.get("note_cliente"),
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
    monkeypatch.setattr(scheduler_module, "invia_promemoria_cliente", lambda **kw: inviati_email.append(kw) or True)
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
    monkeypatch.setattr(scheduler_module, "invia_promemoria_cliente", lambda **kw: inviati.append(kw) or True)
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
    monkeypatch.setattr(scheduler_module, "invia_promemoria_cliente", lambda **kw: inviati.append(kw) or True)
    monkeypatch.setattr(scheduler_module, "invia_promemoria_discord", lambda **kw: None)

    utente = crea_utente_db(db)
    slot = crea_slot(db, scheduler_module.ora_utc_naive() + timedelta(hours=2))
    crea_prenotazione_db(db, utente, slot, reminder_sent=True)

    risultato = scheduler_module.controlla_e_invia_promemoria()

    assert risultato == 0
    assert inviati == []


def test_il_promemoria_discord_riceve_servizio_e_note(db, monkeypatch):
    """Le note non sono più sul calendario (voce 39): il coach le legge qui, il giorno prima."""
    finge_sessione_scheduler(monkeypatch)
    inviati_discord = []
    monkeypatch.setattr(scheduler_module, "invia_promemoria_cliente", lambda **kw: True)
    monkeypatch.setattr(scheduler_module, "invia_promemoria_discord", lambda **kw: inviati_discord.append(kw))

    utente = crea_utente_db(db)
    slot = crea_slot(db, scheduler_module.ora_utc_naive() + timedelta(hours=2))
    crea_prenotazione_db(db, utente, slot, note_cliente="Uso Trick Room con Indeedee-F")

    scheduler_module.controlla_e_invia_promemoria()

    assert inviati_discord[0]["note_cliente"] == "Uso Trick Room con Indeedee-F"
    assert inviati_discord[0]["service_type"] == "vod_review"


def test_promemoria_fallito_non_segnato_e_ritentato(db, monkeypatch):
    """Se Gmail fallisce il promemoria resta da inviare, e il coach non riceve Discord a ogni tentativo."""
    finge_sessione_scheduler(monkeypatch)
    esiti = [False, True]
    inviati_discord = []
    monkeypatch.setattr(scheduler_module, "invia_promemoria_cliente", lambda **kw: esiti.pop(0))
    monkeypatch.setattr(scheduler_module, "invia_promemoria_discord", lambda **kw: inviati_discord.append(kw))

    utente = crea_utente_db(db)
    slot = crea_slot(db, scheduler_module.ora_utc_naive() + timedelta(hours=2))
    prenotazione = crea_prenotazione_db(db, utente, slot)

    scheduler_module.controlla_e_invia_promemoria()
    db.refresh(prenotazione)
    assert prenotazione.reminder_sent is False
    assert inviati_discord == []

    scheduler_module.controlla_e_invia_promemoria()
    db.refresh(prenotazione)
    assert prenotazione.reminder_sent is True
    assert len(inviati_discord) == 1


# ─── controlla_e_invia_richieste_recensione ───────────────────

def test_richiesta_recensione_inviata_per_sessione_conclusa(db, monkeypatch):
    finge_sessione_scheduler(monkeypatch)
    inviate = []
    monkeypatch.setattr(scheduler_module, "invia_richiesta_recensione", lambda **kw: inviate.append(kw) or True)

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
    monkeypatch.setattr(scheduler_module, "invia_richiesta_recensione", lambda **kw: inviate.append(kw) or True)

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

class SchedulerFinto:
    """Registra job, impostazioni e ascoltatori invece di avviare uno scheduler vero.

    Un BackgroundScheduler vero farebbe partire un thread che, a orario,
    eseguirebbe i job contro il database e i servizi esterni reali.
    """

    def __init__(self, **opzioni):
        self.opzioni = opzioni
        self.job = {}
        self.ascoltatori = []

    def add_job(self, funzione, trigger, **opzioni):
        self.job[opzioni["id"]] = (funzione, trigger, opzioni)

    def add_listener(self, funzione, maschera):
        self.ascoltatori.append((funzione, maschera))

    def start(self):
        pass


def avvia_scheduler_finto(monkeypatch):
    monkeypatch.setattr(scheduler_module, "BackgroundScheduler", SchedulerFinto)
    return scheduler_module.avvia_scheduler()


def leggi_job_registrati(monkeypatch):
    return avvia_scheduler_finto(monkeypatch).job


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


def test_lo_scheduler_registra_i_cinque_job(monkeypatch):
    """Dal 4.6a i tre job degli slot non esistono più: generazione notturna,
    sincronizzazione con Google Calendar e pulizia degli slot passati. Le ore
    si calcolano a ogni richiesta, e non c'è più niente da preparare di notte."""
    job = leggi_job_registrati(monkeypatch)

    assert set(job) == {
        "controlla_promemoria", "controlla_recensioni", "controlla_credenziali",
        "controlla_retention_clienti", "backup_database",
    }


def test_la_retention_resta_giornaliera_alle_tre_e_un_minuto(monkeypatch):
    """Solo credenziali e backup sono settimanali. L'orario resta quello di
    sempre anche senza il job delle 03:00 che la precedeva: spostarlo
    cambierebbe l'ora reale del job (CLAUDE.md, NON TOCCARE)."""
    _, trigger, opzioni = leggi_job_registrati(monkeypatch)["controlla_retention_clienti"]

    assert trigger == "cron"
    assert "day_of_week" not in opzioni
    assert (opzioni["hour"], opzioni["minute"]) == (3, 1)


def test_l_avviso_di_calendar_descrive_il_guasto_vero():
    """Con Calendar giù il sito non mostra nessuna ora (pezzo 4.4).

    Fino al 4.6a l'avviso diceva che gli impegni "non bloccano più gli
    slot": falso dal 4.4, e un avviso che descrive il guasto sbagliato
    porta a cercare la riparazione sbagliata.
    """
    calendar = next(c for c in scheduler_module.CREDENZIALI_SORVEGLIATE if c.nome == "Calendar")

    assert "nessuna ora" in calendar.cosa_si_ferma
    assert "slot" not in calendar.cosa_si_ferma

# ─── Sorveglianza dei job (voce 47) ───────────────────────────
#
# Un job che falliva lasciava solo una riga nei log: sei degli otto job non
# avevano nessun avviso. E uno partito con più di un secondo di ritardo
# veniva saltato in silenzio, senza nemmeno fallire.

def evento(codice, id_job="controlla_retention_clienti", eccezione=None):
    """L'annuncio che APScheduler manda agli ascoltatori dopo un'esecuzione."""
    return JobExecutionEvent(codice, id_job, "default", datetime.now(timezone.utc), exception=eccezione)


def raccogli_avvisi(monkeypatch):
    avvisi = []
    monkeypatch.setattr(scheduler_module, "_ultimo_esito_job", {})
    monkeypatch.setattr(scheduler_module, "invia_alert_sistema", lambda t, d: avvisi.append((t, d)))
    return avvisi


def test_un_job_riuscito_dopo_l_avvio_non_avvisa(monkeypatch):
    avvisi = raccogli_avvisi(monkeypatch)

    scheduler_module.sorveglia_job(evento(EVENT_JOB_EXECUTED))

    assert avvisi == []


def test_un_job_che_continua_a_fallire_avvisa_una_volta_sola(monkeypatch):
    avvisi = raccogli_avvisi(monkeypatch)

    for _ in range(3):
        scheduler_module.sorveglia_job(evento(EVENT_JOB_ERROR, eccezione=RuntimeError("guasto")))

    assert len(avvisi) == 1
    titolo, descrizione = avvisi[0]
    assert "controlla_retention_clienti" in titolo
    assert "RuntimeError" in descrizione


def test_l_avviso_non_contiene_il_testo_dell_errore(monkeypatch):
    """Il testo di un errore del database riporta i valori della query: un'email finirebbe su Discord."""
    avvisi = raccogli_avvisi(monkeypatch)

    scheduler_module.sorveglia_job(evento(
        EVENT_JOB_ERROR, eccezione=RuntimeError("Duplicate entry 'mario.rossi@example.com' for key 'email'")
    ))

    titolo, descrizione = avvisi[0]
    assert "mario.rossi@example.com" not in titolo + descrizione


def test_un_job_che_torna_a_funzionare_avvisa_e_poi_tace(monkeypatch):
    avvisi = raccogli_avvisi(monkeypatch)

    scheduler_module.sorveglia_job(evento(EVENT_JOB_ERROR, eccezione=RuntimeError()))
    scheduler_module.sorveglia_job(evento(EVENT_JOB_EXECUTED))
    scheduler_module.sorveglia_job(evento(EVENT_JOB_EXECUTED))

    assert len(avvisi) == 2
    assert "di nuovo funzionante" in avvisi[1][0]


def test_ogni_job_ha_il_proprio_stato(monkeypatch):
    """Il guasto di un job non deve zittire l'avviso di un altro."""
    avvisi = raccogli_avvisi(monkeypatch)

    scheduler_module.sorveglia_job(evento(EVENT_JOB_ERROR, id_job="controlla_retention_clienti", eccezione=RuntimeError()))
    scheduler_module.sorveglia_job(evento(EVENT_JOB_ERROR, id_job="controlla_promemoria", eccezione=RuntimeError()))

    assert len(avvisi) == 2


def test_avvia_scheduler_tollera_i_ritardi_e_registra_l_ascoltatore(monkeypatch):
    scheduler = avvia_scheduler_finto(monkeypatch)

    # Uguaglianza esatta e non "contiene": nessuna timezone deve comparire
    # fra le opzioni, perché sposterebbe l'orario reale di tutti i job (CLAUDE.md).
    assert scheduler.opzioni == {"job_defaults": scheduler_module.TOLLERANZA_RITARDI}
    assert scheduler.ascoltatori == [(scheduler_module.sorveglia_job, scheduler_module.EVENTI_SORVEGLIATI)]


def test_un_job_in_ritardo_parte_e_il_suo_errore_arriva_all_ascoltatore(monkeypatch):
    """
    Con uno scheduler APScheduler vero, configurato come in avvia_scheduler.
    Il job è previsto dieci minuti fa: con la tolleranza di default (1 s)
    veniva saltato senza eseguirlo né avvisare; ora parte, fallisce, e
    l'avviso arriva.
    """
    arrivato = threading.Event()
    avvisi = []
    monkeypatch.setattr(scheduler_module, "_ultimo_esito_job", {})

    def registra(titolo, descrizione):
        avvisi.append(titolo)
        arrivato.set()

    monkeypatch.setattr(scheduler_module, "invia_alert_sistema", registra)

    def job_che_fallisce():
        raise RuntimeError("guasto simulato")

    scheduler = BackgroundScheduler(job_defaults=scheduler_module.TOLLERANZA_RITARDI)
    scheduler.add_listener(scheduler_module.sorveglia_job, scheduler_module.EVENTI_SORVEGLIATI)
    scheduler.add_job(
        job_che_fallisce, "date",
        run_date=datetime.now(timezone.utc) - timedelta(minutes=10),
        id="job_in_ritardo",
    )
    scheduler.start()
    try:
        assert arrivato.wait(timeout=10), "il job in ritardo non è partito, o il suo errore non è arrivato all'ascoltatore"
    finally:
        scheduler.shutdown(wait=True)

    assert avvisi == ["Job job_in_ritardo non riuscito"]
