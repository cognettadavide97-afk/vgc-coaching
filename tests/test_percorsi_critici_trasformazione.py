# Percorsi critici — TRASFORMAZIONE.
#
# Qui il dato è già dentro: questi test documentano cosa gli succede
# mentre viene rielaborato. Tre trasformazioni sono coperte:
#
#   1. calendario Google -> stato degli slot (sincronizza_slot_con_calendario)
#   2. cambio di stato di una prenotazione -> disponibilità dello slot
#      (PATCH /admin/prenotazioni/{id}/stato + libera_slot_prenotazione)
#   3. cancellazione e anonimizzazione del cliente -> righe collegate
#      (DELETE /admin/clienti/{id}, anonimizza_clienti_inattivi)
#
# Come negli altri file "percorsi critici", il test fotografa il
# comportamento ATTUALE. Le asserzioni precedute da COMPORTAMENTO SOSPETTO
# descrivono qualcosa che oggi funziona così ma probabilmente non dovrebbe:
# il test passa lo stesso, e serve da allarme se qualcuno lo cambia senza
# accorgersene.

from datetime import datetime, timedelta, timezone

import pytest

from backend.models.booking import Booking
from backend.models.client_note import ClientNote
from backend.models.package import Package
from backend.models.slots import Slot
from backend.models.users import User
from backend.services import calendar_service
from backend.services.booking_service import libera_slot_prenotazione
from backend.services.calendar_service import (
    leggi_eventi_calendario,
    sincronizza_slot_con_calendario,
)
from backend.services.retention_service import anonimizza_clienti_inattivi
from conftest import admin_headers, crea_slot

ORA = datetime.now(timezone.utc).replace(tzinfo=None)


# ─── 1. DAL CALENDARIO GOOGLE ALLO STATO DEGLI SLOT ──────────
#
# Il servizio Google non viene mai contattato: al suo posto c'è questo
# finto client, che restituisce gli eventi che il test decide. Serve a
# provare la TRASFORMAZIONE (evento -> intervallo UTC -> slot bloccato),
# non la libreria di Google.

class ServizioCalendarioFinto:
    """Imita la catena service.events().list(...).execute() usata dal codice."""

    def __init__(self, eventi):
        self._eventi = eventi
        self.parametri_ultima_lettura = None

    def events(self):
        return self

    def list(self, **kwargs):
        self.parametri_ultima_lettura = kwargs
        return self

    def execute(self):
        return {"items": self._eventi}


def evento_con_orario(inizio_iso, fine_iso):
    return {"start": {"dateTime": inizio_iso}, "end": {"dateTime": fine_iso}}


def evento_giornata_intera(data_inizio, data_fine):
    return {"start": {"date": data_inizio}, "end": {"date": data_fine}}


@pytest.fixture
def calendario(monkeypatch):
    """Installa il calendario finto e permette di deciderne gli eventi."""
    def con_eventi(eventi):
        servizio = ServizioCalendarioFinto(eventi)
        monkeypatch.setattr(calendar_service, "get_calendar_service", lambda: servizio)
        return servizio
    return con_eventi


def test_evento_sul_calendario_blocca_lo_slot_sovrapposto(db, calendario):
    """Un impegno del coach rende non prenotabile lo slot che ci finisce dentro."""
    # Slot alle 15:00 italiane (13:00 UTC d'estate) fra una settimana.
    inizio = ORA + timedelta(days=7)
    slot = crea_slot(db, inizio)

    calendario([evento_con_orario(
        (inizio - timedelta(minutes=30)).isoformat() + "+00:00",
        (inizio + timedelta(minutes=30)).isoformat() + "+00:00",
    )])

    bloccati = sincronizza_slot_con_calendario(db)

    assert bloccati == 1
    db.refresh(slot)
    assert slot.is_available is False
    # blocked_external distingue il blocco automatico da quello manuale.
    assert slot.blocked_external is True


def test_slot_fuori_dallevento_resta_prenotabile(db, calendario):
    """La sovrapposizione è sugli intervalli, non sul giorno."""
    inizio = ORA + timedelta(days=7)
    slot = crea_slot(db, inizio)

    # Evento che finisce esattamente quando lo slot comincia: gli estremi
    # che si toccano non contano come sovrapposizione.
    calendario([evento_con_orario(
        (inizio - timedelta(hours=2)).isoformat() + "+00:00",
        inizio.isoformat() + "+00:00",
    )])

    bloccati = sincronizza_slot_con_calendario(db)

    assert bloccati == 0
    db.refresh(slot)
    assert slot.is_available is True


def test_evento_di_una_giornata_intera_blocca_la_giornata_italiana(db, calendario):
    """"Tutto il giorno" su Google non ha orario: viene esteso al giorno di Roma.

    Il 15 luglio 2030 Roma è UTC+2, quindi la giornata italiana va dalle
    22:00 UTC del 14 alle 22:00 UTC del 15. Uno slot alle 23:00 italiane
    (21:00 UTC) di quel giorno deve rientrarci, e uno del giorno dopo no.
    """
    dentro = crea_slot(db, datetime(2030, 7, 15, 21, 0))     # 23:00 italiane del 15
    fuori = crea_slot(db, datetime(2030, 7, 16, 13, 0))      # 15:00 italiane del 16

    calendario([evento_giornata_intera("2030-07-15", "2030-07-16")])

    bloccati = sincronizza_slot_con_calendario(db)

    assert bloccati == 1
    db.refresh(dentro)
    db.refresh(fuori)
    assert dentro.is_available is False
    assert fuori.is_available is True


def test_evento_in_formato_inatteso_viene_saltato_senza_fermare_la_sync(db, calendario):
    """Un evento privo sia di dateTime sia di date non blocca gli altri."""
    inizio = ORA + timedelta(days=7)
    slot = crea_slot(db, inizio)

    calendario([
        {"start": {}, "end": {}},                            # formato inatteso
        evento_con_orario(
            (inizio - timedelta(minutes=30)).isoformat() + "+00:00",
            (inizio + timedelta(minutes=30)).isoformat() + "+00:00",
        ),
    ])

    bloccati = sincronizza_slot_con_calendario(db)

    assert bloccati == 1
    db.refresh(slot)
    assert slot.is_available is False


def test_calendario_irraggiungibile_non_blocca_nulla_e_non_solleva(db, monkeypatch):
    """Se Google non risponde, la sincronizzazione lascia tutto com'è.

    È una scelta dichiarata (calendar_service.py:146-147): meglio non
    bloccare che fallire.
    """
    slot = crea_slot(db, ORA + timedelta(days=7))

    def esplode():
        raise RuntimeError("Google non raggiungibile")

    monkeypatch.setattr(calendar_service, "get_calendar_service", esplode)

    bloccati = sincronizza_slot_con_calendario(db)

    assert bloccati == 0
    db.refresh(slot)
    assert slot.is_available is True

    # COMPORTAMENTO SOSPETTO: l'errore finisce solo nei log e la funzione
    # restituisce una lista vuota, indistinguibile da "nessun impegno in
    # agenda". Il pannello mostra "0 slot bloccati" anche quando la
    # sincronizzazione non è mai avvenuta.
    assert leggi_eventi_calendario(ORA, ORA + timedelta(days=1)) == []


def test_lo_slot_bloccato_non_viene_riaperto_quando_levento_sparisce(db, calendario):
    """Il blocco automatico è a senso unico: si mette, non si toglie."""
    inizio = ORA + timedelta(days=7)
    slot = crea_slot(db, inizio)

    calendario([evento_con_orario(
        (inizio - timedelta(minutes=30)).isoformat() + "+00:00",
        (inizio + timedelta(minutes=30)).isoformat() + "+00:00",
    )])
    sincronizza_slot_con_calendario(db)
    db.refresh(slot)
    assert slot.is_available is False

    # Il coach cancella l'impegno dal proprio calendario e si sincronizza
    # di nuovo: l'agenda ora è vuota.
    calendario([])
    sincronizza_slot_con_calendario(db)
    db.refresh(slot)

    # COMPORTAMENTO SOSPETTO: lo slot resta chiuso per sempre. La query di
    # sincronizzazione considera solo gli slot con is_available == True
    # (calendar_service.py:204-207), quindi uno slot già bloccato non viene
    # mai più esaminato, e in tutto il backend non esiste una riga che
    # riporti blocked_external o blocked_admin a False. Nemmeno il pannello
    # offre una via d'uscita: il pulsante di eliminazione compare solo per
    # gli slot disponibili (frontend/js/admin.js:855).
    assert slot.is_available is False
    assert slot.blocked_external is True


def test_uno_slot_bloccato_non_e_nemmeno_eliminabile_se_ha_uno_storico(client, db, calendario):
    """L'unica altra uscita — eliminare lo slot — è chiusa se è già stato usato."""
    inizio = ORA + timedelta(days=7)
    slot = crea_slot(db, inizio)

    utente = User(nome="Cliente", email="c@example.com", categoria="senior")
    db.add(utente)
    db.commit()
    # Una prenotazione cancellata in passato basta a legare lo slot allo storico.
    db.add(Booking(user_id=utente.id, slot_id=slot.id, duration_hours=1,
                   price_cents=2000, service_type="vod_review", status="cancelled"))
    db.commit()

    res = client.delete(f"/admin/slots/{slot.id}", headers=admin_headers())

    # COMPORTAMENTO SOSPETTO: preservare lo storico è ragionevole, ma
    # sommato all'impossibilità di sbloccare uno slot (test precedente)
    # significa che quell'orario esce definitivamente dalla vendita, senza
    # alcuna azione possibile dall'interfaccia.
    assert res.status_code == 400
    assert db.query(Slot).filter(Slot.id == slot.id).first() is not None


# ─── 2. CAMBIO DI STATO -> DISPONIBILITÀ DELLO SLOT ──────────

def prenota(db, utente, slot, status="confirmed"):
    prenotazione = Booking(
        user_id=utente.id, slot_id=slot.id, duration_hours=1,
        price_cents=2000, service_type="vod_review", status=status
    )
    slot.is_available = False
    db.add(prenotazione)
    db.commit()
    db.refresh(prenotazione)
    return prenotazione


def crea_utente_db(db, email, nome="Cliente"):
    utente = User(nome=nome, email=email, categoria="senior")
    db.add(utente)
    db.commit()
    db.refresh(utente)
    return utente


def test_cancellare_dal_pannello_libera_lo_slot(client, db):
    """Il caso normale: cancellata la prenotazione, l'orario torna in vendita."""
    utente = crea_utente_db(db, "cliente@example.com")
    slot = crea_slot(db, ORA + timedelta(days=7))
    prenotazione = prenota(db, utente, slot)

    res = client.patch(f"/admin/prenotazioni/{prenotazione.id}/stato",
                       json={"nuovo_stato": "cancelled"}, headers=admin_headers())

    assert res.status_code == 200, res.text
    db.refresh(slot)
    db.refresh(prenotazione)
    assert prenotazione.status == "cancelled"
    assert slot.is_available is True


def test_no_show_non_rimette_lo_slot_in_vendita(client, db):
    """no_show riguarda una sessione già passata: lo slot resta occupato."""
    utente = crea_utente_db(db, "cliente@example.com")
    slot = crea_slot(db, ORA + timedelta(days=7))
    prenotazione = prenota(db, utente, slot)

    res = client.patch(f"/admin/prenotazioni/{prenotazione.id}/stato",
                       json={"nuovo_stato": "no_show"}, headers=admin_headers())

    assert res.status_code == 200, res.text
    db.refresh(slot)
    assert slot.is_available is False


def test_cancellare_due_volte_libera_lo_slot_di_un_altro_cliente(client, db):
    """Cancellare una prenotazione già cancellata tocca lo slot di chi è subentrato."""
    primo = crea_utente_db(db, "primo@example.com", nome="Primo")
    secondo = crea_utente_db(db, "secondo@example.com", nome="Secondo")
    slot = crea_slot(db, ORA + timedelta(days=7))

    prenotazione_primo = prenota(db, primo, slot)
    client.patch(f"/admin/prenotazioni/{prenotazione_primo.id}/stato",
                 json={"nuovo_stato": "cancelled"}, headers=admin_headers())

    # Lo slot è tornato libero e il secondo cliente lo prende.
    db.refresh(slot)
    assert slot.is_available is True
    prenotazione_secondo = prenota(db, secondo, slot)

    # L'admin cancella di nuovo la PRIMA prenotazione (pagina rimasta
    # aperta con dati vecchi, doppio click, chiamata diretta all'API).
    res = client.patch(f"/admin/prenotazioni/{prenotazione_primo.id}/stato",
                       json={"nuovo_stato": "cancelled"}, headers=admin_headers())
    assert res.status_code == 200, res.text

    db.refresh(slot)
    db.refresh(prenotazione_secondo)

    # COMPORTAMENTO SOSPETTO: aggiorna_stato non guarda lo stato di
    # partenza (admin/bookings.py:113-117), quindi libera lo slot ogni
    # volta che il nuovo stato è "cancelled". Lo slot del secondo cliente
    # torna prenotabile mentre la sua prenotazione è ancora confermata: da
    # qui in avanti due clienti possono ritrovarsi sullo stesso orario, e
    # la riserva atomica di booking.py:178-187 — che è la difesa contro la
    # doppia prenotazione — viene aggirata da questa strada.
    assert slot.is_available is True
    assert prenotazione_secondo.status == "confirmed"


def test_riportare_a_confermata_una_prenotazione_cancellata_non_ri_riserva_lo_slot(client, db):
    """La transizione cancelled -> confirmed è ammessa e non riserva niente."""
    utente = crea_utente_db(db, "cliente@example.com")
    slot = crea_slot(db, ORA + timedelta(days=7))
    prenotazione = prenota(db, utente, slot)

    client.patch(f"/admin/prenotazioni/{prenotazione.id}/stato",
                 json={"nuovo_stato": "cancelled"}, headers=admin_headers())
    res = client.patch(f"/admin/prenotazioni/{prenotazione.id}/stato",
                       json={"nuovo_stato": "confirmed"}, headers=admin_headers())

    assert res.status_code == 200, res.text
    db.refresh(prenotazione)
    db.refresh(slot)

    # COMPORTAMENTO SOSPETTO: la prenotazione risulta di nuovo confermata,
    # ma il suo slot è rimasto libero e prenotabile da chiunque. Nessun
    # errore viene mostrato: il pannello risponde "Stato aggiornato a
    # confirmed".
    assert prenotazione.status == "confirmed"
    assert slot.is_available is True


def test_lidentificativo_dellevento_viene_azzerato_anche_se_google_non_risponde(db, monkeypatch):
    """libera_slot_prenotazione dimentica l'evento senza sapere se è stato cancellato."""
    utente = crea_utente_db(db, "cliente@example.com")
    slot = crea_slot(db, ORA + timedelta(days=7))
    prenotazione = prenota(db, utente, slot)
    prenotazione.calendar_event_id = "evento_google_123"
    db.commit()

    # Google irraggiungibile: elimina_evento_calendario cattura l'errore al
    # proprio interno e non restituisce nulla (calendar_service.py:243-244).
    def esplode():
        raise RuntimeError("Google non raggiungibile")

    monkeypatch.setattr(calendar_service, "get_calendar_service", esplode)

    libera_slot_prenotazione(prenotazione, db)
    db.commit()
    db.refresh(prenotazione)

    # COMPORTAMENTO SOSPETTO: l'esito dell'eliminazione non è osservabile
    # dal chiamante, che azzera comunque calendar_event_id. L'evento resta
    # sull'agenda del coach e nessuno conserva più il suo id: l'unico modo
    # di rimuoverlo diventa cancellarlo a mano da Google Calendar.
    assert prenotazione.calendar_event_id is None
    db.refresh(slot)
    assert slot.is_available is True


# ─── 3. CANCELLAZIONE E ANONIMIZZAZIONE DEL CLIENTE ──────────

def test_cancellare_un_cliente_con_pacchetto_elimina_i_pacchetti_prima_delle_prenotazioni(client, db):
    """L'ordine reale degli statement è l'opposto di quello del codice.

    `db.delete(p)` accoda soltanto: l'SQL parte al commit. Il bulk delete
    dei pacchetti, invece, va al database subito. Con autoflush disattivato
    (backend/database.py:28) i pacchetti vengono quindi cancellati mentre
    le prenotazioni che li referenziano esistono ancora.
    """
    from sqlalchemy import event
    from conftest import TEST_ENGINE

    utente = crea_utente_db(db, "cliente@example.com")
    slot = crea_slot(db, ORA + timedelta(days=7))
    pacchetto = Package(user_id=utente.id, tipo="starter", sessioni_totali=4,
                        sessioni_usate=1, durata_sessione_ore=1, prezzo_cents=7000)
    db.add(pacchetto)
    db.commit()
    db.refresh(pacchetto)

    prenotazione = prenota(db, utente, slot)
    prenotazione.package_id = pacchetto.id
    db.commit()

    statement_eseguiti = []

    def registra_statement(conn, cursor, statement, parameters, context, executemany):
        statement_eseguiti.append(" ".join(statement.split()))

    event.listen(TEST_ENGINE, "before_cursor_execute", registra_statement)
    try:
        res = client.delete(f"/admin/clienti/{utente.id}", headers=admin_headers())
    finally:
        event.remove(TEST_ENGINE, "before_cursor_execute", registra_statement)

    assert res.status_code == 200, res.text

    def prima_occorrenza(frammento):
        for indice, statement in enumerate(statement_eseguiti):
            if frammento in statement:
                return indice
        raise AssertionError(f"nessuno statement contiene {frammento!r}")

    # COMPORTAMENTO SOSPETTO: DELETE FROM packages viene eseguito PRIMA di
    # DELETE FROM bookings, cioè mentre le prenotazioni referenziano ancora
    # il pacchetto. Su SQLite passa perché la suite gira senza i vincoli di
    # chiave esterna attivi (PRAGMA foreign_keys resta OFF); su MySQL, dove
    # il vincolo fk_bookings_package_id esiste davvero, lo stesso ordine
    # produce l'errore 1451 e un 500 al pannello, con il cliente NON
    # cancellato. È l'endpoint che implementa il diritto all'oblio.
    assert prima_occorrenza("DELETE FROM packages") < prima_occorrenza("DELETE FROM bookings")

    assert db.query(User).filter(User.id == utente.id).first() is None
    assert db.query(Package).count() == 0
    assert db.query(Booking).count() == 0


def test_anonimizzare_un_cliente_non_ripulisce_note_e_prenotazioni(db):
    """L'anonimizzazione tocca solo la riga `users`."""
    vecchio = ORA - timedelta(days=800)   # oltre i 24 mesi di RETENTION_MONTHS

    utente = User(nome="Mario Rossi", email="mario.rossi@example.com",
                  telefono="333123456", categoria="senior", created_at=vecchio)
    db.add(utente)
    db.commit()
    db.refresh(utente)

    slot = Slot(start_time=vecchio, duration_hours=1, is_available=False)
    db.add(slot)
    db.commit()
    db.refresh(slot)

    db.add(Booking(
        user_id=utente.id, slot_id=slot.id, duration_hours=1, price_cents=2000,
        service_type="vod_review", status="confirmed", created_at=vecchio,
        note_cliente="Sono Mario Rossi, il mio Discord è mario#1234",
    ))
    db.add(ClientNote(user_id=utente.id, nota="Mario preferisce le sessioni serali",
                      created_at=vecchio))
    db.commit()

    assert anonimizza_clienti_inattivi(db) == 1

    db.refresh(utente)
    assert utente.nome == "Cliente anonimizzato"
    assert utente.telefono is None

    nota = db.query(ClientNote).first()
    prenotazione = db.query(Booking).first()

    # COMPORTAMENTO SOSPETTO: il nome e il contatto Discord del cliente
    # restano leggibili in chiaro nelle note interne e nelle note di
    # prenotazione, entrambe campi di testo libero scritti da persone.
    # Il cliente risulta "anonimizzato" pur essendo ancora identificabile
    # da altre due tabelle.
    assert "Mario" in nota.nota
    assert "Mario Rossi" in prenotazione.note_cliente
