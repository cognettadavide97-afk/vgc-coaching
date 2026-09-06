# Copre backend/services/availability_service.py e la parte di
# backend/routers/admin/availability.py legata alle regole ricorrenti —
# finora senza nessun test dedicato. Vedi tests/conftest.py per come sono
# preparati client/db.

from datetime import date, datetime, time

from backend.models.slots import Slot
from backend.models.users import User
from backend.models.booking import Booking
from backend.models.availability_rule import AvailabilityRule
from backend.models.availability_exception import AvailabilityException
from backend.services.availability_service import (
    applica_blocco_eccezionale,
    elimina_slot_obsoleti,
    genera_slot_da_regola,
)
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


# ─── BLOCCHI ECCEZIONALI (FERIE) ──────────────────────────────
# applica_blocco_eccezionale è il punto in cui "sono via dal 10 al 15"
# diventa un insieme di slot davvero bloccati. Il rischio non è ovvio:
# gli slot sono salvati in UTC, ma il periodo che il coach indica è in
# GIORNI ITALIANI. Chi confrontasse le date senza convertire otterrebbe
# uno scarto di un'ora (due d'estate) proprio sui bordi — cioè slot
# ancora prenotabili mentre il coach è via, o chiusi un giorno di troppo.
# I test qui sotto stanno tutti su quei bordi, ed è il motivo per cui
# usano orari a cavallo della mezzanotte invece di orari comodi.

def blocco(db, data_inizio, data_fine, motivo="Ferie"):
    """Crea il blocco sul database e lo applica, come fa l'endpoint POST."""
    eccezione = AvailabilityException(data_inizio=data_inizio, data_fine=data_fine, motivo=motivo)
    db.add(eccezione)
    db.commit()
    db.refresh(eccezione)
    return eccezione, applica_blocco_eccezionale(eccezione, db)


def test_blocco_estivo_copre_il_giorno_italiano_non_quello_utc(db):
    """Ora legale: Roma è UTC+2, quindi il 10 luglio italiano inizia alle 22:00 UTC del 9.

    Lo slot delle 22:30 UTC del 9 luglio è già "10 luglio sera" per il
    coach e deve essere bloccato; quello delle 21:30 è ancora il 9 e non
    deve esserlo. È la coppia che smaschera un confronto fatto sulle date
    UTC senza conversione.
    """
    dentro = crea_slot(db, datetime(2030, 7, 9, 22, 30))    # Roma: 10 luglio 00:30
    fuori = crea_slot(db, datetime(2030, 7, 9, 21, 30))     # Roma: 9 luglio 23:30

    _, bloccati = blocco(db, date(2030, 7, 10), date(2030, 7, 15))

    assert bloccati == 1
    db.refresh(dentro); db.refresh(fuori)
    assert dentro.is_available is False and dentro.blocked_admin is True
    assert fuori.is_available is True


def test_blocco_estivo_copre_lultimo_giorno_fino_a_mezzanotte_italiana(db):
    """L'estremo finale è incluso per intero, non troncato alle 00:00."""
    dentro = crea_slot(db, datetime(2030, 7, 15, 21, 30))   # Roma: 15 luglio 23:30
    fuori = crea_slot(db, datetime(2030, 7, 15, 22, 30))    # Roma: 16 luglio 00:30

    _, bloccati = blocco(db, date(2030, 7, 10), date(2030, 7, 15))

    assert bloccati == 1
    db.refresh(dentro); db.refresh(fuori)
    assert dentro.is_available is False
    assert fuori.is_available is True


def test_blocco_invernale_usa_lo_scarto_giusto_e_non_uno_fisso(db):
    """Stessa scena in ora solare, dove Roma è UTC+1 invece di UTC+2.

    Le 22:30 UTC del 9 gennaio sono ancora il 9 in Italia (23:30), mentre
    le stesse 22:30 UTC del 9 luglio erano già il 10. Se la conversione
    usasse uno scarto fisso invece del fuso reale, uno dei due test della
    coppia fallirebbe.
    """
    fuori = crea_slot(db, datetime(2030, 1, 9, 22, 30))     # Roma: 9 gennaio 23:30
    dentro = crea_slot(db, datetime(2030, 1, 9, 23, 30))    # Roma: 10 gennaio 00:30

    _, bloccati = blocco(db, date(2030, 1, 10), date(2030, 1, 10))

    assert bloccati == 1
    db.refresh(dentro); db.refresh(fuori)
    assert dentro.is_available is False
    assert fuori.is_available is True


def test_blocco_non_tocca_gli_slot_gia_prenotati(db):
    """Una prenotazione confermata resta valida anche se il coach blocca il periodo.

    Il blocco agisce solo su ciò che è ancora libero: annullare una
    sessione già venduta è una decisione umana, non un effetto collaterale.
    """
    prenotato = crea_slot(db, datetime(2030, 7, 12, 10, 0), is_available=False)
    libero = crea_slot(db, datetime(2030, 7, 12, 11, 0))

    _, bloccati = blocco(db, date(2030, 7, 10), date(2030, 7, 15))

    assert bloccati == 1
    db.refresh(prenotato)
    # Non è stato ri-toccato: resta occupato, ma non marcato come blocco admin.
    assert prenotato.is_available is False and prenotato.blocked_admin is False
    db.refresh(libero)
    assert libero.blocked_admin is True


def test_blocco_di_un_solo_giorno_non_sconfina(db):
    prima = crea_slot(db, datetime(2030, 7, 11, 12, 0))
    dentro = crea_slot(db, datetime(2030, 7, 12, 12, 0))
    dopo = crea_slot(db, datetime(2030, 7, 13, 12, 0))

    _, bloccati = blocco(db, date(2030, 7, 12), date(2030, 7, 12))

    assert bloccati == 1
    db.refresh(prima); db.refresh(dentro); db.refresh(dopo)
    assert dentro.is_available is False
    assert prima.is_available is True and dopo.is_available is True


# ─── CRUD di regole e blocchi, dal lato HTTP ──────────────────
# Le funzioni sopra sono provate direttamente; qui si prova che gli
# endpoint le colleghino davvero — validazione degli estremi, conteggio
# restituito, e le due cancellazioni, che hanno un comportamento
# volutamente asimmetrico rispetto agli slot già toccati.

def test_crea_blocco_rifiuta_un_periodo_alla_rovescia(client, db):
    res = client.post(
        "/admin/disponibilita/blocchi",
        headers=admin_headers(),
        json={"data_inizio": "2030-07-15", "data_fine": "2030-07-10", "motivo": "Ferie"}
    )
    assert res.status_code == 400


def test_crea_blocco_di_un_giorno_solo_e_ammesso(client, db):
    """data_fine uguale a data_inizio è valido: è l'indisponibilità di un giorno."""
    res = client.post(
        "/admin/disponibilita/blocchi",
        headers=admin_headers(),
        json={"data_inizio": "2030-07-10", "data_fine": "2030-07-10"}
    )
    assert res.status_code == 200


def test_crea_blocco_riporta_quanti_slot_ha_chiuso(client, db):
    crea_slot(db, datetime(2030, 7, 12, 10, 0))
    crea_slot(db, datetime(2030, 7, 12, 11, 0))
    crea_slot(db, datetime(2030, 8, 12, 10, 0))    # fuori periodo

    res = client.post(
        "/admin/disponibilita/blocchi",
        headers=admin_headers(),
        json={"data_inizio": "2030-07-10", "data_fine": "2030-07-15", "motivo": "Ferie"}
    )

    assert res.status_code == 200
    corpo = res.json()
    assert corpo["slot_bloccati"] == 2
    assert corpo["blocco"]["motivo"] == "Ferie"


def test_lista_blocchi_mostra_prima_i_piu_recenti(client, db):
    for inizio in ("2030-07-10", "2030-09-10", "2030-08-10"):
        client.post(
            "/admin/disponibilita/blocchi",
            headers=admin_headers(),
            json={"data_inizio": inizio, "data_fine": inizio}
        )

    res = client.get("/admin/disponibilita/blocchi", headers=admin_headers())

    assert res.status_code == 200
    date_inizio = [b["data_inizio"] for b in res.json()]
    assert date_inizio == ["2030-09-10", "2030-08-10", "2030-07-10"]


def test_elimina_blocco_inesistente_risponde_404(client, db):
    res = client.delete("/admin/disponibilita/blocchi/9999", headers=admin_headers())
    assert res.status_code == 404


def test_elimina_blocco_non_riapre_gli_slot_che_aveva_chiuso(client, db):
    """Comportamento voluto, non dimenticanza.

    Riaprire in automatico rimetterebbe in vendita orari che il coach
    potrebbe aver chiuso anche per altri motivi; la riapertura è una
    decisione esplicita. Il test lo fissa perché è controintuitivo, e
    senza una prova qualcuno lo "correggerebbe" in buona fede.
    """
    slot = crea_slot(db, datetime(2030, 7, 12, 10, 0))
    creato = client.post(
        "/admin/disponibilita/blocchi",
        headers=admin_headers(),
        json={"data_inizio": "2030-07-10", "data_fine": "2030-07-15"}
    ).json()

    res = client.delete(f"/admin/disponibilita/blocchi/{creato['blocco']['id']}", headers=admin_headers())

    assert res.status_code == 200
    db.refresh(slot)
    assert slot.is_available is False and slot.blocked_admin is True


def test_crea_regola_rifiuta_ora_fine_non_successiva(client, db):
    res = client.post(
        "/admin/disponibilita/regole",
        headers=admin_headers(),
        json={"giorno_settimana": 1, "ora_inizio": "22:00:00", "ora_fine": "22:00:00", "durata_slot_ore": 1}
    )
    assert res.status_code == 400


def test_lista_regole_ordinata_per_giorno_e_ora(client, db):
    for giorno, ora in ((3, "18:00:00"), (1, "20:00:00"), (1, "18:00:00")):
        client.post(
            "/admin/disponibilita/regole",
            headers=admin_headers(),
            json={"giorno_settimana": giorno, "ora_inizio": ora, "ora_fine": "23:00:00", "durata_slot_ore": 1}
        )

    res = client.get("/admin/disponibilita/regole", headers=admin_headers())

    assert res.status_code == 200
    assert [(r["giorno_settimana"], r["ora_inizio"]) for r in res.json()] == [
        (1, "18:00:00"), (1, "20:00:00"), (3, "18:00:00")
    ]


def test_elimina_regola_inesistente_risponde_404(client, db):
    res = client.delete("/admin/disponibilita/regole/9999", headers=admin_headers())
    assert res.status_code == 404


def test_elimina_regola_non_cancella_gli_slot_gia_generati(client, db):
    """Gli slot generati diventano indipendenti dalla regola che li ha creati.

    Altrimenti togliere una regola cancellerebbe orari già pubblicati, e
    potenzialmente già prenotabili, senza che nessuno lo abbia chiesto.
    """
    creata = client.post(
        "/admin/disponibilita/regole",
        headers=admin_headers(),
        json={"giorno_settimana": 1, "ora_inizio": "18:00:00", "ora_fine": "20:00:00", "durata_slot_ore": 1}
    ).json()
    slot_prima = db.query(Slot).count()
    assert slot_prima > 0    # la regola ha davvero generato qualcosa

    res = client.delete(f"/admin/disponibilita/regole/{creata['regola']['id']}", headers=admin_headers())

    assert res.status_code == 200
    assert db.query(Slot).count() == slot_prima
