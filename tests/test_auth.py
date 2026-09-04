# Copre due zone che la suite lasciava scoperte pur essendo il perimetro di
# sicurezza dell'applicazione (vedi STATO_PROGETTO.md, §18):
#
# 1. POST /admin/login. Gli altri test admin non ci passano mai: conftest
#    costruisce il token direttamente con crea_token('admin'), che è comodo
#    ma salta l'unico punto in cui la password viene davvero controllata.
#    Un errore in verifica_credenziali non avrebbe fatto fallire nulla.
#
# 2. Il rifiuto di un token PRESENTE ma non valido. I 401 già esistenti
#    (test_admin.py) chiamano senza header Authorization, quindi il rifiuto
#    scatta nello schema OAuth2 di FastAPI prima di arrivare al nostro
#    codice. I casi reali — token scaduto, firma rifatta con un'altra
#    chiave, token studente speso su un endpoint admin — non erano provati.

from datetime import datetime, timedelta

import bcrypt
from jose import jwt

import backend.services.auth_service as auth_service
from backend.services.auth_service import crea_token, crea_token_studente

PASSWORD = "password-di-prova-solo-per-i-test"
# Endpoint admin qualsiasi: qui interessa il controllo del token, non cosa
# risponde l'endpoint quando lo supera.
ENDPOINT_ADMIN = "/admin/export/csv"


def configura_admin(monkeypatch, username="coach", password=PASSWORD):
    """Imposta credenziali admin note per la durata del singolo test.

    ADMIN_USERNAME e ADMIN_PASSWORD_HASH sono variabili di modulo lette da
    .env all'import: si sostituiscono lì, non nell'ambiente.
    """
    hash_bcrypt = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    monkeypatch.setattr(auth_service, "ADMIN_USERNAME", username)
    monkeypatch.setattr(auth_service, "ADMIN_PASSWORD_HASH", hash_bcrypt)


# ─── POST /admin/login ────────────────────────────────────────

def test_login_con_credenziali_valide_restituisce_un_token_che_apre_il_pannello(client, monkeypatch):
    configura_admin(monkeypatch)

    res = client.post("/admin/login", data={"username": "coach", "password": PASSWORD})

    assert res.status_code == 200
    corpo = res.json()
    assert corpo["token_type"] == "bearer"
    # Il token non è solo "presente": deve funzionare davvero su un endpoint
    # protetto. Senza questa seconda chiamata il test passerebbe anche se
    # crea_token emettesse un token con il claim `type` sbagliato.
    res_protetto = client.get(
        ENDPOINT_ADMIN, headers={"Authorization": f"Bearer {corpo['access_token']}"}
    )
    assert res_protetto.status_code == 200


def test_login_con_password_sbagliata_viene_rifiutato(client, monkeypatch):
    configura_admin(monkeypatch)

    res = client.post("/admin/login", data={"username": "coach", "password": "password-sbagliata"})

    assert res.status_code == 401
    assert "access_token" not in res.json()


def test_login_con_username_sbagliato_viene_rifiutato(client, monkeypatch):
    """La password giusta non basta: deve combaciare anche l'utente."""
    configura_admin(monkeypatch)

    res = client.post("/admin/login", data={"username": "qualcun-altro", "password": PASSWORD})

    assert res.status_code == 401


def test_login_negato_se_lhash_non_e_configurato(client, monkeypatch):
    """Un deploy senza ADMIN_PASSWORD_HASH non deve diventare un pannello aperto.

    È il caso di una variabile dimenticata su un ambiente nuovo: senza il
    controllo esplicito in verifica_credenziali, bcrypt riceverebbe un hash
    vuoto e il comportamento dipenderebbe dalla libreria.
    """
    monkeypatch.setattr(auth_service, "ADMIN_USERNAME", "coach")
    monkeypatch.setattr(auth_service, "ADMIN_PASSWORD_HASH", None)

    res = client.post("/admin/login", data={"username": "coach", "password": PASSWORD})

    assert res.status_code == 401


# ─── Token presente ma non valido ─────────────────────────────

def token_admin_scaduto():
    dati = {
        "sub": "admin",
        "type": "admin",
        "exp": datetime.utcnow() - timedelta(minutes=1),
    }
    return jwt.encode(dati, auth_service.SECRET_KEY, algorithm=auth_service.ALGORITHM)


def test_token_admin_scaduto_viene_rifiutato(client):
    res = client.get(ENDPOINT_ADMIN, headers={"Authorization": f"Bearer {token_admin_scaduto()}"})

    assert res.status_code == 401


def test_token_firmato_con_unaltra_chiave_viene_rifiutato(client):
    """Un token ben formato ma firmato da chi non conosce JWT_SECRET.

    È la forma che assumerebbe un token fabbricato da un attaccante: la
    struttura è giusta, manca solo la firma valida.
    """
    dati = {
        "sub": "admin",
        "type": "admin",
        "exp": datetime.utcnow() + timedelta(minutes=60),
    }
    falso = jwt.encode(dati, "chiave-che-il-server-non-conosce", algorithm=auth_service.ALGORITHM)

    res = client.get(ENDPOINT_ADMIN, headers={"Authorization": f"Bearer {falso}"})

    assert res.status_code == 401


def test_token_studente_non_vale_come_token_admin(client):
    """La separazione dei due tipi di token, provata dal lato che conta.

    Studente e admin sono firmati con la stessa chiave: senza il controllo
    sul claim `type`, un token studente sarebbe strutturalmente accettabile
    dagli endpoint del pannello. Questo test è la prova che non lo è.
    """
    token = crea_token_studente(user_id=1, email="studente@example.com")

    res = client.get(ENDPOINT_ADMIN, headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 401


def test_token_admin_non_vale_come_token_studente(client):
    """E la stessa separazione nella direzione opposta."""
    res = client.get("/users/me", cookies={"student_token": crea_token("admin")})

    assert res.status_code == 401
