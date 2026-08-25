# Copre il fix di sicurezza sul parametro "state" del login Discord (vedi
# backend/routers/discord_auth.py): senza, un attaccante poteva iniettare
# il proprio "code" OAuth nel browser della vittima e farla autenticare
# con l'account Discord dell'attaccante (login CSRF). Le chiamate vere a
# Discord (scambio del code, lettura del profilo) sono finte via
# monkeypatch — nessuna richiesta di rete reale in questi test, stesso
# principio delle integrazioni finte in tests/conftest.py.

from urllib.parse import urlparse, parse_qs

import backend.routers.discord_auth as discord_auth_router
from backend.models.users import User


class RispostaFinta:
    """Sostituisce requests.Response quanto basta per questi test: un
    .json() che restituisce dati preparati, e un .raise_for_status() che
    non fa nulla (simula "richiesta andata a buon fine")."""
    def __init__(self, dati):
        self._dati = dati

    def raise_for_status(self):
        pass

    def json(self):
        return self._dati


def finge_scambio_discord(monkeypatch, discord_id="999888777", email="studente@example.com", username="studentetest"):
    monkeypatch.setattr(
        discord_auth_router.requests, "post",
        lambda *a, **k: RispostaFinta({"access_token": "token-finto"})
    )
    monkeypatch.setattr(
        discord_auth_router.requests, "get",
        lambda *a, **k: RispostaFinta({
            "id": discord_id, "email": email,
            "username": username, "discriminator": "0"
        })
    )


def stato_da_redirect(location):
    """Estrae il valore di ?state=... da un URL di redirect."""
    return parse_qs(urlparse(location).query)["state"][0]


def test_login_imposta_cookie_state_e_lo_include_nel_redirect(client):
    res = client.get("/auth/discord/login", follow_redirects=False)

    assert res.status_code in (302, 307)
    assert "discord_oauth_state" in res.cookies
    assert res.cookies["discord_oauth_state"] == stato_da_redirect(res.headers["location"])


def test_callback_senza_cookie_state_viene_rifiutato(client, db, monkeypatch):
    # Nessuna chiamata precedente a /login su questo client: non esiste
    # nessun cookie discord_oauth_state — simula esattamente un attaccante
    # che manda alla vittima un link diretto a /callback con un suo code.
    finge_scambio_discord(monkeypatch)

    res = client.get("/auth/discord/callback?code=abc&state=qualsiasi", follow_redirects=False)

    assert res.headers["location"] == "/?discord_error=1"
    assert db.query(User).count() == 0  # nessun login/utente creato


def test_callback_con_state_diverso_dal_cookie_viene_rifiutato(client, db, monkeypatch):
    finge_scambio_discord(monkeypatch)

    login_res = client.get("/auth/discord/login", follow_redirects=False)
    assert "discord_oauth_state" in login_res.cookies  # il cookie ora è nel client.cookies

    res = client.get("/auth/discord/callback?code=abc&state=valore-diverso", follow_redirects=False)

    assert res.headers["location"] == "/?discord_error=1"
    assert db.query(User).count() == 0


def test_callback_con_state_corretto_completa_il_login(client, db, monkeypatch):
    finge_scambio_discord(monkeypatch, discord_id="42", email="nuovo@example.com", username="nuovostudente")

    login_res = client.get("/auth/discord/login", follow_redirects=False)
    state = stato_da_redirect(login_res.headers["location"])

    res = client.get(f"/auth/discord/callback?code=abc&state={state}", follow_redirects=False)

    assert res.status_code in (302, 307)
    # Il token non passa più nell'URL di redirect: è impostato come cookie
    # httpOnly (vedi backend/routers/discord_auth.py) — invisibile a
    # JavaScript, ma il test può comunque leggerlo da res.cookies per
    # verificare che sia stato impostato davvero.
    assert res.headers["location"] == "/"
    assert "student_token" in res.cookies

    utente = db.query(User).filter(User.email == "nuovo@example.com").first()
    assert utente is not None
    assert utente.discord_id == "42"
