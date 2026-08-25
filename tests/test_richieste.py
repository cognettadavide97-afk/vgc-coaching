# Copre backend/routers/consulenza.py e backend/routers/pacchetti_richieste.py
# — entrambi endpoint pubblici "solo contatti" (nessun pagamento in-app,
# nessuna prenotazione vera creata), finora senza nessun test dedicato.
# Le email/Discord che questi router chiamano sono finte tramite
# tests/conftest.py (integrazioni_esterne_finte) — indispensabile qui,
# perché a differenza di booking.py questi due router non erano ancora
# coperti da quel mocking prima di questo fix.

from backend.models.users import User


def test_richiedi_consulenza_crea_utente_e_risponde_ok(client, db):
    res = client.post("/consulenze/", json={
        "nome": "Luigi",
        "email": "luigi.consulenza@example.com",
        "discord_tag": "luigi#0001",
        "messaggio": "Vorrei capire da dove iniziare"
    })

    assert res.status_code == 200, res.text

    # get_or_create_user (backend/routers/users.py) traccia il cliente
    # anche per questo canale, così se in futuro prenota una sessione vera
    # con la stessa email lo ritrova invece di duplicarlo.
    utente = db.query(User).filter(User.email == "luigi.consulenza@example.com").first()
    assert utente is not None
    assert utente.nome == "Luigi"


def test_richiedi_consulenza_senza_messaggio_facoltativo(client, db):
    # messaggio e discord_tag sono Optional (vedi backend/schemas/consulenza.py)
    res = client.post("/consulenze/", json={
        "nome": "Peach",
        "email": "peach.consulenza@example.com"
    })
    assert res.status_code == 200, res.text


def test_richiedi_consulenza_email_non_valida_viene_rifiutata(client, db):
    res = client.post("/consulenze/", json={
        "nome": "Bowser",
        "email": "non-e-una-email"
    })
    assert res.status_code == 422  # validazione Pydantic (EmailStr), prima ancora del nostro codice


def test_richiedi_pacchetto_crea_utente_e_risponde_ok(client, db):
    res = client.post("/pacchetti-richieste/", json={
        "nome": "Mario",
        "email": "mario.pacchetto@example.com",
        "discord_tag": "mario#0001",
        "tipo": "intro",
        "messaggio": "Interessato al pacchetto introduttivo"
    })

    assert res.status_code == 200, res.text

    utente = db.query(User).filter(User.email == "mario.pacchetto@example.com").first()
    assert utente is not None


def test_richiedi_pacchetto_tipo_non_valido_viene_rifiutato(client, db):
    # "tipo" è un Literal["intro", "team", "tour"] (vedi
    # backend/schemas/pacchetto_richiesta.py) — un valore fuori catalogo
    # deve essere rifiutato dalla validazione, non arrivare al nostro codice
    # (che userebbe CATALOGO_PACCHETTI[tipo] e solleverebbe un KeyError
    # invece di un errore chiaro al client).
    res = client.post("/pacchetti-richieste/", json={
        "nome": "Wario",
        "email": "wario@example.com",
        "tipo": "non-esiste"
    })
    assert res.status_code == 422
