# Copre backend/routers/admin/availability.py: regole ricorrenti e blocchi
# eccezionali, dal lato del pannello. Vedi tests/conftest.py per come sono
# preparati client/db.
#
# Dal pezzo 4.6a regole e blocchi non generano né chiudono slot: si salvano
# e basta, e le ore in vendita le calcola services/disponibilita_service.py
# a ogni richiesta. Qui si prova che gli endpoint salvino e validino, e che
# ogni modifica valga subito per il calcolo. Fino ad allora questo file
# provava la generazione degli slot, il loro blocco e lo sblocco a mano:
# quei test sono spariti con il codice che provavano.

from datetime import date, datetime, time

from backend.models.availability_exception import AvailabilityException
from backend.models.availability_rule import AvailabilityRule
from backend.services.disponibilita_service import calcola_disponibilita
from conftest import admin_headers

# Martedì 16 luglio 2030, d'estate: le 18:00 italiane sono le 16:00 UTC.
MARTEDI = date(2030, 7, 16)
INIZIO_MARTEDI = datetime(2030, 7, 16, 0, 0)
FINE_MARTEDI = datetime(2030, 7, 17, 0, 0)


def crea_regola(client, giorno=1, inizio="18:00:00", fine="20:00:00"):
    return client.post(
        "/admin/disponibilita/regole",
        headers=admin_headers(),
        json={"giorno_settimana": giorno, "ora_inizio": inizio, "ora_fine": fine, "durata_slot_ore": 1}
    )


def ore_in_vendita(db, da, a):
    """Le ore da 1 ora che il calcolo offre fra `da` e `a` (UTC naive)."""
    return calcola_disponibilita(db, da, a)[1]


# ─── REGOLE RICORRENTI ────────────────────────────────────────

def test_regola_con_durata_diversa_da_1_ora_viene_rifiutata(client, db):
    """
    Le regole hanno solo ore da 1 ora: le sessioni da 2 ore uniscono due ore
    consecutive, ogni 2 ore dall'inizio della regola (calcola_disponibilita
    in backend/services/disponibilita_service.py). Fino al pezzo 4.3 una
    regola con durata_slot_ore=2 avrebbe generato slot reali da 2h che
    saltavano il vincolo sull'orario di inizio (allora 15:00/17:00) —
    bloccata qui, non solo omessa dal form admin.
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


def test_creare_una_regola_restituisce_la_regola_salvata(client, db):
    """Solo la regola: dal 4.6a non c'è più un conteggio di slot generati."""
    res = crea_regola(client)

    assert res.status_code == 200, res.text
    corpo = res.json()
    assert corpo["giorno_settimana"] == 1
    assert corpo["ora_inizio"] == "18:00:00"
    assert corpo["attiva"] is True
    assert db.query(AvailabilityRule).filter(AvailabilityRule.id == corpo["id"]).count() == 1


def test_crea_regola_rifiuta_ora_fine_non_successiva(client, db):
    res = crea_regola(client, inizio="22:00:00", fine="22:00:00")
    assert res.status_code == 400


def test_lista_regole_ordinata_per_giorno_e_ora(client, db):
    for giorno, ora in ((3, "18:00:00"), (1, "20:00:00"), (1, "18:00:00")):
        crea_regola(client, giorno=giorno, inizio=ora, fine="23:00:00")

    res = client.get("/admin/disponibilita/regole", headers=admin_headers())

    assert res.status_code == 200
    assert [(r["giorno_settimana"], r["ora_inizio"]) for r in res.json()] == [
        (1, "18:00:00"), (1, "20:00:00"), (3, "18:00:00")
    ]


def test_elimina_regola_inesistente_risponde_404(client, db):
    res = client.delete("/admin/disponibilita/regole/9999", headers=admin_headers())
    assert res.status_code == 404


def test_una_regola_vale_subito_e_una_volta_eliminata_non_vale_piu(client, db):
    """Nessun job da aspettare né slot da ripulire: il calcolo legge le regole a ogni richiesta.

    Fino al 4.6a eliminare una regola lasciava in vendita gli slot che
    aveva già generato, fino a fine mese.
    """
    regola = crea_regola(client).json()
    assert ore_in_vendita(db, INIZIO_MARTEDI, FINE_MARTEDI) == [datetime(2030, 7, 16, 16), datetime(2030, 7, 16, 17)]

    res = client.delete(f"/admin/disponibilita/regole/{regola['id']}", headers=admin_headers())

    assert res.status_code == 200
    assert ore_in_vendita(db, INIZIO_MARTEDI, FINE_MARTEDI) == []


def test_una_regola_legacy_da_2_ore_non_produce_ore(db):
    """Salvata prima del vincolo sulla durata: non produce ore invece di produrne di sbagliate."""
    db.add(AvailabilityRule(giorno_settimana=1, ora_inizio=time(18), ora_fine=time(22), durata_slot_ore=2))
    db.commit()

    assert calcola_disponibilita(db, INIZIO_MARTEDI, FINE_MARTEDI) == {1: [], 2: []}


# ─── BLOCCHI ECCEZIONALI ──────────────────────────────────────

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


def test_creare_un_blocco_restituisce_il_blocco_salvato(client, db):
    """Solo il blocco: dal 4.6a non c'è più un conteggio di slot chiusi."""
    res = client.post(
        "/admin/disponibilita/blocchi",
        headers=admin_headers(),
        json={"data_inizio": "2030-07-10", "data_fine": "2030-07-15", "motivo": "Ferie"}
    )

    assert res.status_code == 200, res.text
    corpo = res.json()
    assert corpo["motivo"] == "Ferie"
    assert corpo["data_inizio"] == "2030-07-10"
    assert db.query(AvailabilityException).filter(AvailabilityException.id == corpo["id"]).count() == 1


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


def test_un_blocco_chiude_subito_i_suoi_giorni_e_eliminato_li_riapre(client, db):
    """Il contrario di come funzionava con gli slot.

    Fino al 4.6a eliminare un blocco non riapriva gli slot che aveva chiuso:
    il blocco non sapeva quali fossero, e si sbloccavano uno per uno a mano.
    Il calcolo invece legge i blocchi a ogni richiesta, e un secondo blocco
    sovrapposto resta in vigore da solo.
    """
    crea_regola(client)
    blocco = client.post(
        "/admin/disponibilita/blocchi",
        headers=admin_headers(),
        json={"data_inizio": "2030-07-16", "data_fine": "2030-07-16", "motivo": "Ferie"}
    ).json()
    assert ore_in_vendita(db, INIZIO_MARTEDI, FINE_MARTEDI) == []

    res = client.delete(f"/admin/disponibilita/blocchi/{blocco['id']}", headers=admin_headers())

    assert res.status_code == 200
    assert len(ore_in_vendita(db, INIZIO_MARTEDI, FINE_MARTEDI)) == 2


# ─── IL BLOCCO SEGUE IL GIORNO ITALIANO ───────────────────────
# Le ore sono salvate e confrontate in UTC, ma il periodo che il coach
# indica è in GIORNI ITALIANI. Chi confrontasse le date senza convertire
# otterrebbe uno scarto di un'ora (due d'estate) proprio sui bordi: ore
# ancora prenotabili mentre il coach è via, o chiuse un giorno di troppo.
# I test qui sotto stanno su quei bordi, con regole a cavallo della
# mezzanotte italiana. Fino al 4.6a provavano lo stesso fatto sugli slot
# (applica_blocco_eccezionale).

def regola_db(db, giorno_settimana, inizio, fine):
    db.add(AvailabilityRule(giorno_settimana=giorno_settimana, ora_inizio=time(inizio),
                            ora_fine=time(fine), durata_slot_ore=1))
    db.commit()


def blocco_db(db, data_inizio, data_fine):
    db.add(AvailabilityException(data_inizio=data_inizio, data_fine=data_fine, motivo="Ferie"))
    db.commit()


def test_il_blocco_estivo_copre_il_giorno_italiano_non_quello_utc(db):
    """Ora legale: Roma è UTC+2, quindi il 10 luglio italiano inizia alle 22:00 UTC del 9.

    La mezzanotte italiana del 10 (22:00 UTC del 9) è già nelle ferie;
    le 22:00 italiane del 9 (20:00 UTC) no. È la coppia che smaschera un
    confronto fatto sulle date UTC senza conversione.
    """
    regola_db(db, 1, 22, 23)    # martedì 9 luglio, 22:00 italiane
    regola_db(db, 2, 0, 1)      # mercoledì 10 luglio, 00:00 italiane
    blocco_db(db, date(2030, 7, 10), date(2030, 7, 15))

    assert ore_in_vendita(db, datetime(2030, 7, 9), datetime(2030, 7, 10, 6)) == [datetime(2030, 7, 9, 20)]


def test_il_blocco_estivo_copre_l_ultimo_giorno_fino_a_mezzanotte_italiana(db):
    """L'estremo finale è incluso per intero, non troncato alle 00:00 UTC."""
    regola_db(db, 0, 22, 23)    # lunedì 15 luglio, 22:00 italiane: ancora ferie
    regola_db(db, 1, 0, 1)      # martedì 16 luglio, 00:00 italiane: 22:00 UTC del 15, ferie finite
    blocco_db(db, date(2030, 7, 10), date(2030, 7, 15))

    assert ore_in_vendita(db, datetime(2030, 7, 15), datetime(2030, 7, 16, 6)) == [datetime(2030, 7, 15, 22)]


def test_il_blocco_invernale_usa_lo_scarto_giusto_e_non_uno_fisso(db):
    """Stessa scena in ora solare, dove Roma è UTC+1 invece di UTC+2.

    Se la conversione usasse uno scarto fisso invece del fuso reale, uno
    dei due test, l'estivo o questo, fallirebbe.
    """
    regola_db(db, 2, 22, 23)    # mercoledì 9 gennaio, 22:00 italiane = 21:00 UTC
    regola_db(db, 3, 0, 1)      # giovedì 10 gennaio, 00:00 italiane = 23:00 UTC del 9
    blocco_db(db, date(2030, 1, 10), date(2030, 1, 10))

    assert ore_in_vendita(db, datetime(2030, 1, 9), datetime(2030, 1, 10, 6)) == [datetime(2030, 1, 9, 21)]


# ─── ENDPOINT DEGLI SLOT ──────────────────────────────────────

def test_gli_endpoint_degli_slot_del_pannello_non_esistono_piu(client, db):
    """Lista, sincronizzazione, eliminazione e sblocco degli slot, e la creazione a mano.

    Il pannello non li chiama dal 4.5b; dal 4.6a non esistono. GET /slots/
    resta fino al 4.6b per le pagine vecchie nella cache dei browser, quindi
    POST sullo stesso indirizzo risponde 405 e non 404.
    """
    chiamate = [
        client.get("/admin/slots", headers=admin_headers()),
        client.post("/admin/slots/sync-calendario", headers=admin_headers()),
        client.delete("/admin/slots/1", headers=admin_headers()),
        client.post("/admin/slots/1/sblocca", headers=admin_headers()),
        client.post("/slots/", headers=admin_headers(), json={"start_time": "2030-07-15T18:00:00", "duration_hours": 1}),
    ]

    assert [r.status_code for r in chiamate] == [404, 404, 404, 404, 405]
