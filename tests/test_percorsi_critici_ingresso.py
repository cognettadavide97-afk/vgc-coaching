# Percorsi critici — INGRESSO DEI DATI.
#
# Questo file documenta come il sistema accetta i dati che arrivano da
# fuori: registrazione del cliente (POST /users/) e creazione della
# prenotazione (POST /bookings/). Sono i punti in cui un valore scritto dal
# browser entra nel database, e quindi quelli in cui un comportamento
# inatteso si propaga a tutto il resto. Fino al pezzo 4.6a c'era anche la
# creazione dello slot dal pannello (POST /slots/), sparita con gli slot:
# l'ora italiana delle regole la provano i test del calcolo
# (tests/test_disponibilita.py, test_l_ora_legale_sposta_l_orario_utc).
#
# I test NON dicono come il sistema dovrebbe comportarsi: dicono come si
# comporta oggi. Dove il comportamento attuale è discutibile il test passa
# comunque, e sopra l'asserzione c'è un commento COMPORTAMENTO SOSPETTO che
# spiega il perché — così una modifica futura che lo cambia si vede subito,
# invece di passare inosservata.
#
# Vedi tests/conftest.py per database di test e integrazioni esterne finte.

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from backend.models.booking import Booking
from backend.models.users import User
from conftest import admin_headers, apri_ore, iso

ROME_TZ = ZoneInfo("Europe/Rome")


def rome_naive_utc(anno, mese, giorno, ora):
    """Orario italiano -> datetime naive in UTC, come viene salvato nel DB."""
    return datetime(anno, mese, giorno, ora, tzinfo=ROME_TZ).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


# Un lunedì alle 15:00 italiane, ben nel futuro: orario di inizio valido
# anche per le sessioni da 2 ore (vedi ORE_INIZIO_VALIDE_2H in booking.py).
INIZIO = rome_naive_utc(2030, 1, 7, 15)


def registra(client, email, nome="Cliente Test"):
    res = client.post("/users/", json={
        "nome": nome,
        "email": email,
        "categoria": "senior",
        "discord_tag": None,
        "telefono": None
    })
    assert res.status_code == 200, res.text
    return res.json()["id"]


# ─── REGISTRAZIONE: POST /users/ è un "get or create" pubblico ───

def test_registrarsi_due_volte_con_la_stessa_email_non_crea_un_secondo_utente(client, db):
    """La seconda registrazione con la stessa email riusa la riga esistente.

    È il comportamento su cui si regge il form pubblico: chi ha già
    prenotato in passato non deve ricevere un errore "email già presente".
    """
    primo = registra(client, "mario@example.com", nome="Mario")
    secondo = registra(client, "mario@example.com", nome="Nome Diverso")

    assert primo == secondo
    assert db.query(User).count() == 1

    # I dati della prima registrazione restano: il secondo invio non
    # aggiorna nome, categoria o telefono.
    utente = db.query(User).first()
    assert utente.nome == "Mario"


def test_chi_conosce_lemail_di_un_cliente_ne_ottiene_lid_dallendpoint_pubblico(client, db):
    """POST /users/ restituisce l'id di un utente PREESISTENTE a chiunque.

    L'endpoint è pubblico e non richiede alcuna prova di possesso
    dell'indirizzo.
    """
    id_vittima = registra(client, "vittima@example.com", nome="Vittima")

    # Un secondo chiamante, che conosce solo l'email, invia dati inventati.
    id_ottenuto = registra(client, "vittima@example.com", nome="Attaccante")

    # COMPORTAMENTO SOSPETTO: la coppia (user_id, email) è l'unica difesa di
    # create_booking nel flusso senza login (backend/routers/booking.py:102),
    # ma l'id si ottiene dall'email tramite questo stesso endpoint pubblico.
    # Chi conosce l'email di un cliente ha quindi entrambi i valori e può
    # prenotare a suo nome (vedi il test seguente).
    assert id_ottenuto == id_vittima


def test_si_puo_prenotare_a_nome_di_un_altro_conoscendone_solo_lemail(client, db):
    """Il flusso completo dell'impersonazione, in due chiamate pubbliche."""
    id_vittima = registra(client, "vittima@example.com", nome="Vittima")
    apri_ore(db, INIZIO)

    res = client.post("/bookings/", json={
        "user_id": id_vittima,
        "email": "vittima@example.com",
        "start_time": iso(INIZIO),
        "duration_hours": 1,
        "service_type": "vod_review"
    })

    # COMPORTAMENTO SOSPETTO: la prenotazione va a buon fine senza alcuna
    # verifica del possesso dell'indirizzo. Consuma il limite di 2
    # prenotazioni attive della vittima, le fa arrivare un'email di
    # conferma e occupa un'ora reale.
    assert res.status_code == 200, res.text
    assert res.json()["user_id"] == id_vittima


def test_email_con_maiuscole_diverse_ritrova_lo_stesso_utente(client, db):
    """L'email entra in minuscolo, quindi il confronto non dipende dal motore.

    Prima `get_or_create_user` (backend/routers/users.py:107) confrontava
    l'email così come scritta, e l'esito dipendeva dalla collation: su
    SQLite (case-sensitive) nascevano due clienti per la stessa persona, su
    MySQL (case-insensitive) tornava l'utente esistente, la cui email non
    coincideva con quella digitata, e la prenotazione finiva nel 403 "user_id
    and email do not match" (booking.py:102). Ora EmailNormalizzata
    (backend/schemas/users.py) la mette in minuscolo all'ingresso (voce 9).
    """
    primo = registra(client, "mario@example.com")
    secondo = registra(client, "Mario@Example.com")

    assert primo == secondo
    assert db.query(User).count() == 1


# ─── PRENOTAZIONE: cosa il server accetta e cosa decide da sé ───

def test_il_prezzo_inviato_dal_client_viene_ignorato(client, db):
    """Il listino è del server: un prezzo nel corpo non viene nemmeno letto."""
    id_utente = registra(client, "cliente@example.com")
    apri_ore(db, INIZIO)

    res = client.post("/bookings/", json={
        "user_id": id_utente,
        "email": "cliente@example.com",
        "start_time": iso(INIZIO),
        "duration_hours": 1,
        "service_type": "vod_review",
        # Campi non previsti da BookingCreate: Pydantic li scarta in
        # silenzio (comportamento di default, `extra` non è configurato).
        "price_cents": 1,
        "status": "cancelled"
    })

    assert res.status_code == 200, res.text
    prenotazione = res.json()
    assert prenotazione["price_cents"] == 2000   # TABELLA_PREZZI[1]
    assert prenotazione["status"] == "confirmed"


def test_il_limite_di_due_prenotazioni_attive_riparte_da_zero_con_unaltra_email(client, db):
    """Il conteggio è per user.id, e per un ospite l'identità è l'email."""
    id_primo = registra(client, "uno@example.com")
    ore = [INIZIO + timedelta(days=giorni) for giorni in range(3)]
    for ora in ore:
        apri_ore(db, ora)

    for ora in ore[:2]:
        res = client.post("/bookings/", json={
            "user_id": id_primo, "email": "uno@example.com",
            "start_time": iso(ora), "duration_hours": 1, "service_type": "vod_review"
        })
        assert res.status_code == 200, res.text

    # La terza con la stessa email viene respinta: il limite funziona.
    res_terza = client.post("/bookings/", json={
        "user_id": id_primo, "email": "uno@example.com",
        "start_time": iso(ore[2]), "duration_hours": 1, "service_type": "vod_review"
    })
    assert res_terza.status_code == 400

    # La stessa persona con un secondo indirizzo riparte da zero.
    id_secondo = registra(client, "uno+bis@example.com")
    res_aggirata = client.post("/bookings/", json={
        "user_id": id_secondo, "email": "uno+bis@example.com",
        "start_time": iso(ore[2]), "duration_hours": 1, "service_type": "vod_review"
    })

    # COMPORTAMENTO SOSPETTO: MAX_PRENOTAZIONI_ATTIVE (booking.py:34) è
    # presentato come misura anti-abuso, ma per gli ospiti — cioè l'unico
    # flusso in cui il rischio esiste — basta una seconda email gratuita per
    # azzerarlo. Vincola solo gli studenti autenticati.
    assert res_aggirata.status_code == 200, res_aggirata.text


def test_durata_non_a_listino_respinta_prima_di_toccare_il_database(client, db):
    """Una durata fuori da {1, 2} è fermata da Pydantic con un 422."""
    id_utente = registra(client, "cliente@example.com")
    apri_ore(db, INIZIO)

    res = client.post("/bookings/", json={
        "user_id": id_utente, "email": "cliente@example.com",
        "start_time": iso(INIZIO), "duration_hours": 3, "service_type": "vod_review"
    })

    assert res.status_code == 422
    # Nessuna prenotazione: la validazione avviene prima del router.
    assert db.query(Booking).count() == 0
