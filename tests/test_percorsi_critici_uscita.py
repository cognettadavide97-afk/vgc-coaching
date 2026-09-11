# Percorsi critici — USCITA.
#
# Cosa il sistema manda fuori, e in che forma. Quattro destinazioni:
#
#   1. il browser pubblico   -> GET /slots/ (orari con offset esplicito)
#   2. il pannello admin     -> GET /admin/dashboard (numeri di sintesi)
#   3. i servizi esterni     -> Google Calendar, Gmail, webhook Discord
#   4. Google Drive          -> il dump SQL del backup
#
# Nessun servizio esterno viene contattato davvero: al loro posto ci sono
# dei finti che registrano cosa avrebbero ricevuto. È esattamente il punto
# dei test di questo file — non "la chiamata riesce", ma "il contenuto
# spedito è quello atteso".
#
# Le asserzioni precedute da COMPORTAMENTO SOSPETTO fotografano un
# comportamento attuale discutibile, senza cambiarlo.

from datetime import datetime, timedelta, timezone

import pytest

from backend.models.booking import Booking
from backend.models.review import Review
from backend.models.slots import Slot
from backend.models.users import User
from backend.services import calendar_service, discord_service, email_service
from backend.services.backup_service import RIGHE_PER_INSERT, crea_dump_sql
from conftest import admin_headers, crea_slot

ORA = datetime.now(timezone.utc).replace(tzinfo=None)


def crea_utente_db(db, email="cliente@example.com", nome="Cliente"):
    utente = User(nome=nome, email=email, categoria="senior")
    db.add(utente)
    db.commit()
    db.refresh(utente)
    return utente


# ─── 1. VERSO IL BROWSER PUBBLICO ────────────────────────────

def test_gli_slot_pubblici_escono_con_loffset_utc_esplicito(client, db):
    """Il database contiene orari senza fuso: l'API ne dichiara uno in uscita.

    Senza l'offset, il JavaScript del browser leggerebbe "15:00" come ora
    locale del dispositivo e mostrerebbe l'orario sbagliato a chiunque non
    sia su UTC (backend/schemas/slots.py:68-78).
    """
    crea_slot(db, datetime(2030, 7, 15, 13, 0))   # 15:00 italiane, ora legale

    res = client.get("/slots/")

    assert res.status_code == 200, res.text
    assert res.json()[0]["start_time"] == "2030-07-15T13:00:00+00:00"


def test_gli_slot_pubblici_non_espongono_i_motivi_del_blocco(client, db):
    """La risposta pubblica contiene solo i quattro campi di SlotResponse."""
    crea_slot(db, ORA + timedelta(days=7))

    res = client.get("/slots/")

    assert set(res.json()[0].keys()) == {"id", "start_time", "duration_hours", "is_available"}


def test_uno_slot_occupato_non_compare_nella_lista_pubblica(client, db):
    """Il form pubblico riceve solo ciò che è davvero prenotabile."""
    libero = crea_slot(db, ORA + timedelta(days=7))
    crea_slot(db, ORA + timedelta(days=8), is_available=False)
    crea_slot(db, ORA - timedelta(days=1))   # passato, ma ancora is_available=True

    res = client.get("/slots/")

    assert [s["id"] for s in res.json()] == [libero.id]


# ─── 2. VERSO IL PANNELLO ADMIN ──────────────────────────────

def test_la_dashboard_riassume_prenotazioni_incassi_e_voti(client, db):
    """I cinque numeri della schermata iniziale del pannello."""
    utente = crea_utente_db(db)
    slot_passato = crea_slot(db, ORA - timedelta(days=3), is_available=False)
    slot_futuro = crea_slot(db, ORA + timedelta(days=7))

    confermata = Booking(user_id=utente.id, slot_id=slot_passato.id, duration_hours=1,
                         price_cents=2000, service_type="vod_review", status="confirmed")
    db.add(confermata)
    db.commit()
    db.refresh(confermata)
    db.add(Review(booking_id=confermata.id, voto=4, commento="Ottima", approvata=False))
    db.commit()

    res = client.get("/admin/dashboard", headers=admin_headers())

    assert res.status_code == 200, res.text
    dati = res.json()
    assert dati["totale_prenotazioni"] == 1
    assert dati["totale_incassato_euro"] == 20.0        # centesimi / 100
    # La media considera anche le recensioni non ancora approvate: è un
    # dato interno, diverso da quello della vetrina pubblica.
    assert dati["media_voto_recensioni"] == 4.0
    # I prossimi slot liberi escono già formattati in ora italiana.
    assert [s["id"] for s in dati["prossimi_slot_liberi"]] == [slot_futuro.id]
    assert "/" in dati["prossimi_slot_liberi"][0]["data"]   # gg/mm/aaaa


def test_la_dashboard_senza_dati_non_restituisce_valori_nulli_al_posto_degli_zeri(client, db):
    """Database vuoto: somma e media hanno comportamenti diversi."""
    res = client.get("/admin/dashboard", headers=admin_headers())

    dati = res.json()
    assert dati["totale_prenotazioni"] == 0
    assert dati["totale_incassato_euro"] == 0.0
    assert dati["prossimi_slot_liberi"] == []
    # La media resta None (nessuna recensione da mediare): il pannello deve
    # saper distinguere "nessun voto" da "voto zero".
    assert dati["media_voto_recensioni"] is None


def test_una_prenotazione_cancellata_sparisce_dagli_incassi_ma_non_dal_totale(client, db):
    """Le due metriche contano cose diverse."""
    utente = crea_utente_db(db)
    slot = crea_slot(db, ORA + timedelta(days=7), is_available=False)
    db.add(Booking(user_id=utente.id, slot_id=slot.id, duration_hours=1,
                   price_cents=2000, service_type="vod_review", status="cancelled"))
    db.commit()

    dati = client.get("/admin/dashboard", headers=admin_headers()).json()

    assert dati["totale_prenotazioni"] == 1
    assert dati["totale_incassato_euro"] == 0.0


# ─── 3. VERSO I SERVIZI ESTERNI ──────────────────────────────

class ServizioInsertFinto:
    """Imita service.events().insert(...).execute() e conserva il corpo inviato."""

    def __init__(self):
        self.corpo_inviato = None
        self.calendario_usato = None

    def events(self):
        return self

    def insert(self, calendarId=None, body=None):
        self.calendario_usato = calendarId
        self.corpo_inviato = body
        return self

    def execute(self):
        return {"id": "evento_google_123", "htmlLink": "https://calendar.google.com/evento"}


def test_levento_sul_calendario_viene_creato_in_ora_italiana_dichiarata(monkeypatch):
    """Qui, a differenza del resto del progetto, non si converte in UTC.

    L'API di Google accetta un orario locale accompagnato dal nome del
    fuso, quindi l'orario italiano viene spedito così com'è insieme a
    "Europe/Rome" (calendar_service.py:101-119).
    """
    servizio = ServizioInsertFinto()
    monkeypatch.setattr(calendar_service, "get_calendar_service", lambda: servizio)

    event_id = calendar_service.crea_evento_calendario(
        nome_cliente="Mario Rossi",
        email_cliente="mario@example.com",
        categoria="senior",
        data_slot="15/07/2030",
        ora_slot="15:00",
        durata_ore=2,
        note_cliente="Vorrei rivedere la finale",
    )

    assert event_id == "evento_google_123"
    corpo = servizio.corpo_inviato
    assert corpo["summary"] == "Coaching VGC — Mario Rossi"
    assert corpo["start"] == {"dateTime": "2030-07-15T15:00:00", "timeZone": "Europe/Rome"}
    # La fine è calcolata dalla durata: 15:00 + 2 ore.
    assert corpo["end"] == {"dateTime": "2030-07-15T17:00:00", "timeZone": "Europe/Rome"}

    # COMPORTAMENTO SOSPETTO: email e note del cliente finiscono in chiaro
    # nella descrizione di un evento di calendario, che è condiviso con il
    # service account e con chiunque abbia accesso a quel calendario.
    assert "mario@example.com" in corpo["description"]
    assert "Vorrei rivedere la finale" in corpo["description"]


def test_se_google_calendar_fallisce_la_prenotazione_resta_senza_evento(client, db, monkeypatch):
    """L'errore non viene propagato: si perde solo l'evento, non la prenotazione."""
    def esplode():
        raise RuntimeError("Google non raggiungibile")

    monkeypatch.setattr(calendar_service, "get_calendar_service", esplode)

    event_id = calendar_service.crea_evento_calendario(
        nome_cliente="Mario", email_cliente="mario@example.com", categoria="senior",
        data_slot="15/07/2030", ora_slot="15:00", durata_ore=1,
    )

    # COMPORTAMENTO SOSPETTO: None è indistinguibile fra "Google ha
    # rifiutato" e "l'evento non è stato richiesto". La prenotazione viene
    # salvata comunque con calendar_event_id nullo e nessuno viene
    # avvisato: il coach scopre la sessione mancante solo guardando
    # l'agenda.
    assert event_id is None


class InvioEmailFinto:
    """Registra ogni email che sarebbe partita, invece di spedirla."""

    def __init__(self):
        self.inviate = []

    def __call__(self, destinatario, oggetto, corpo_html):
        self.inviate.append({
            "destinatario": destinatario,
            "oggetto": oggetto,
            "corpo": corpo_html,
        })


@pytest.fixture
def email_spedite(monkeypatch):
    finto = InvioEmailFinto()
    monkeypatch.setattr(email_service, "_invia_via_gmail", finto)
    return finto


def test_il_promemoria_al_cliente_contiene_data_ora_e_durata(email_spedite):
    """L'email che parte dallo scheduler poche ore prima della sessione."""
    email_service.invia_promemoria_cliente(
        email_cliente="mario@example.com", nome_cliente="Mario",
        data_slot="15/07/2030", ora_slot="15:00", durata=2,
    )

    assert len(email_spedite.inviate) == 1
    email = email_spedite.inviate[0]
    assert email["destinatario"] == "mario@example.com"
    assert email["oggetto"] == "Reminder: your VGC coaching session is coming up"
    assert "15/07/2030" in email["corpo"]
    assert "2 hours" in email["corpo"]   # plurale calcolato dalla durata


def test_la_richiesta_di_recensione_contiene_il_link_con_il_token(email_spedite):
    """Il link è l'unica credenziale che autorizza a lasciare la recensione."""
    link = "https://esempio.it/static/recensione.html?booking_id=7&token=abc123"

    email_service.invia_richiesta_recensione(
        email_cliente="mario@example.com", nome_cliente="Mario", link_recensione=link,
    )

    corpo = email_spedite.inviate[0]["corpo"]
    assert f'href="{link}"' in corpo


def test_unemail_non_partita_non_interrompe_chi_lha_richiesta(monkeypatch):
    """Ogni funzione di invio cattura le proprie eccezioni."""
    def esplode(*args, **kwargs):
        raise RuntimeError("Gmail non raggiungibile")

    monkeypatch.setattr(email_service, "_invia_via_gmail", esplode)

    # COMPORTAMENTO SOSPETTO: la funzione non restituisce nulla, quindi il
    # chiamante non può distinguere un'email partita da una persa. Un
    # promemoria mai arrivato lascia traccia solo nei log, e la
    # prenotazione risulta comunque "reminder_sent" (backend/scheduler.py).
    assert email_service.invia_promemoria_cliente(
        email_cliente="mario@example.com", nome_cliente="Mario",
        data_slot="15/07/2030", ora_slot="15:00", durata=1,
    ) is None


class PostFinto:
    """Sostituisce requests.post e conserva l'ultima chiamata."""

    def __init__(self):
        self.chiamate = []

    def __call__(self, url, json=None, timeout=None):
        self.chiamate.append({"url": url, "json": json, "timeout": timeout})

        class Risposta:
            def raise_for_status(self_non_usato):
                return None

        return Risposta()


def test_la_notifica_discord_traduce_il_servizio_in_etichetta_leggibile(monkeypatch):
    """Il valore salvato nel database non è quello mostrato nel messaggio."""
    post = PostFinto()
    monkeypatch.setattr(discord_service, "requests", type("M", (), {"post": staticmethod(post)}))
    monkeypatch.setattr(discord_service, "DISCORD_WEBHOOK_URL", "https://discord.test/webhook")

    discord_service.invia_notifica_discord(
        nome_cliente="Mario", discord_tag=None, service_type="vod_review",
        data_slot="15/07/2030", ora_slot="15:00", durata_ore=1, note_cliente=None,
    )

    assert len(post.chiamate) == 1
    chiamata = post.chiamate[0]
    # Il timeout è obbligatorio: questa chiamata avviene dentro la
    # richiesta di prenotazione del cliente.
    assert chiamata["timeout"] == 5
    campi = {c["name"]: c["value"] for c in chiamata["json"]["embeds"][0]["fields"]}
    assert campi["Servizio"] == "VOD Review"
    # I campi vuoti hanno un segnaposto, non restano vuoti.
    assert campi["Discord"] == "non specificato"
    assert campi["Note"] == "nessuna"


def test_senza_webhook_configurato_la_notifica_discord_viene_saltata(monkeypatch):
    """Un'installazione senza Discord non deve fallire, solo non notificare."""
    post = PostFinto()
    monkeypatch.setattr(discord_service, "requests", type("M", (), {"post": staticmethod(post)}))
    monkeypatch.setattr(discord_service, "DISCORD_WEBHOOK_URL", None)

    discord_service.invia_notifica_discord(
        nome_cliente="Mario", discord_tag="mario#1234", service_type="vod_review",
        data_slot="15/07/2030", ora_slot="15:00", durata_ore=1,
    )

    assert post.chiamate == []


# ─── 4. VERSO GOOGLE DRIVE: il dump del backup ───────────────
#
# crea_dump_sql parla direttamente al driver del database con sintassi
# MySQL (SHOW TABLES, SHOW CREATE TABLE): non è eseguibile sullo SQLite
# della suite. Il finto qui sotto riproduce le sole risposte che la
# funzione si aspetta, così il FORMATO del file prodotto resta verificato.

class CursoreFinto:
    def __init__(self, tabelle):
        self._tabelle = tabelle
        self._risultato = None
        self.description = None

    def execute(self, sql):
        if sql == "SHOW TABLES":
            self._risultato = [(nome,) for nome in self._tabelle]
            self.description = None
        elif sql.startswith("SHOW CREATE TABLE"):
            nome = sql.split("`")[1]
            self._risultato = (nome, f"CREATE TABLE `{nome}` (`id` int)")
        elif sql.startswith("SELECT"):
            nome = sql.split("`")[1]
            self._risultato = self._tabelle[nome]
            self.description = [("id",), ("valore",)]

    def fetchall(self):
        return self._risultato

    def fetchone(self):
        return self._risultato


class ConnessioneFinta:
    def __init__(self, tabelle):
        self._tabelle = tabelle
        self.chiusa = False

    def cursor(self):
        return CursoreFinto(self._tabelle)

    def escape(self, valore):
        if valore is None:
            return "NULL"
        if isinstance(valore, str):
            return f"'{valore}'"
        return str(valore)

    def close(self):
        self.chiusa = True


class EngineFinto:
    def __init__(self, tabelle):
        self.connessione = ConnessioneFinta(tabelle)

    def raw_connection(self):
        return self.connessione


def test_il_dump_disattiva_i_vincoli_e_ricrea_ogni_tabella():
    """Struttura del file .sql caricato su Drive."""
    engine = EngineFinto({"users": [(1, "mario"), (2, None)]})

    dump = crea_dump_sql(engine)

    righe = dump.splitlines()
    assert righe[0] == "-- Backup automatico VGC Coaching"
    # I vincoli vanno disattivati durante il ripristino: le tabelle si
    # ricreano in ordine alfabetico, non in ordine di dipendenza.
    assert righe[2] == "SET FOREIGN_KEY_CHECKS=0;"
    assert dump.rstrip().endswith("SET FOREIGN_KEY_CHECKS=1;")
    assert "DROP TABLE IF EXISTS `users`;" in dump
    assert "CREATE TABLE `users` (`id` int);" in dump
    # I valori passano da connessione.escape: le stringhe vengono quotate,
    # i None diventano NULL.
    assert "INSERT INTO `users` (`id`, `valore`) VALUES (1, 'mario'), (2, NULL);" in dump
    # La connessione viene sempre chiusa (blocco finally).
    assert engine.connessione.chiusa is True


def test_le_tabelle_grandi_vengono_spezzate_in_piu_insert():
    """Un INSERT per riga renderebbe il ripristino lentissimo: si va a blocchi."""
    righe_finte = [(i, f"riga{i}") for i in range(RIGHE_PER_INSERT + 1)]
    engine = EngineFinto({"bookings": righe_finte})

    dump = crea_dump_sql(engine)

    assert dump.count("INSERT INTO `bookings`") == 2


def test_una_tabella_vuota_non_produce_nessun_insert():
    engine = EngineFinto({"reviews": []})

    dump = crea_dump_sql(engine)

    assert "INSERT INTO `reviews`" not in dump
    # Struttura sì, però: una tabella vuota va comunque ricreata.
    assert "CREATE TABLE `reviews`" in dump
