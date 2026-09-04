# Copre il fix di sicurezza sull'HTML injection nelle email (vedi
# backend/services/email_service.py, funzione _escape): campi testo libero
# scritti dal cliente (nome, note, messaggio) finiscono nel corpo HTML
# delle email — senza escaping, un cliente potrebbe far comparire un link
# o markup arbitrario nella casella del coach. _invia_via_gmail (che
# farebbe la vera chiamata a Gmail) viene sostituita con una finta che
# cattura solo l'HTML costruito, senza mandare nessuna email vera — stesso
# principio delle integrazioni finte in tests/conftest.py.

import backend.services.email_service as email_service

HTML_MALEVOLO = '<a href="http://sito-malevolo.example">clicca qui</a>'


def cattura_corpo_html(monkeypatch):
    catturato = {}
    monkeypatch.setattr(
        email_service, "_invia_via_gmail",
        lambda destinatario, oggetto, corpo_html: catturato.update(
            destinatario=destinatario, oggetto=oggetto, corpo=corpo_html
        )
    )
    return catturato


def test_note_cliente_con_html_viene_escapato_in_notifica_admin(monkeypatch):
    catturato = cattura_corpo_html(monkeypatch)

    email_service.invia_notifica_admin(
        nome_cliente="Mario <b>Rossi</b>",
        email_cliente="mario@example.com",
        data_slot="01/01/2030",
        ora_slot="15:00",
        durata=1,
        note_cliente=HTML_MALEVOLO
    )

    assert HTML_MALEVOLO not in catturato["corpo"]
    assert "&lt;a href=" in catturato["corpo"]
    assert "&lt;b&gt;Rossi&lt;/b&gt;" in catturato["corpo"]
    # L'oggetto dell'email non è HTML: lì il nome resta quello vero, non
    # ha senso (e sarebbe fuorviante) mostrare "&lt;b&gt;" nell'oggetto.
    assert catturato["oggetto"] == "Nuova prenotazione — Mario <b>Rossi</b>"


def test_messaggio_consulenza_con_html_viene_escapato(monkeypatch):
    catturato = cattura_corpo_html(monkeypatch)

    email_service.invia_notifica_richiesta_consulenza_admin(
        nome_cliente="Luigi",
        email_cliente="luigi@example.com",
        discord_tag="<script>alert(1)</script>",
        messaggio=HTML_MALEVOLO
    )

    assert HTML_MALEVOLO not in catturato["corpo"]
    assert "<script>" not in catturato["corpo"]
    assert "&lt;script&gt;" in catturato["corpo"]


def test_messaggio_pacchetto_con_html_viene_escapato(monkeypatch):
    catturato = cattura_corpo_html(monkeypatch)

    email_service.invia_notifica_richiesta_pacchetto_admin(
        nome_cliente="Peach",
        email_cliente="peach@example.com",
        discord_tag=None,
        nome_pacchetto="Competitive Intro",
        messaggio=HTML_MALEVOLO
    )

    assert HTML_MALEVOLO not in catturato["corpo"]
    assert "&lt;a href=" in catturato["corpo"]
    assert "non specificato" in catturato["corpo"]  # discord_tag mancante, valore di default


def test_nome_cliente_con_html_viene_escapato_in_email_al_cliente(monkeypatch):
    # Le email al cliente stesso sono un vettore meno critico (attaccherebbe
    # solo la propria casella), ma l'escaping è applicato ovunque per
    # coerenza — questo test lo verifica anche lì.
    catturato = cattura_corpo_html(monkeypatch)

    email_service.invia_conferma_cliente(
        email_cliente="mario@example.com",
        nome_cliente="Mario <i>Rossi</i>",
        data_slot="01/01/2030",
        ora_slot="15:00",
        durata=1,
        prezzo=2000
    )

    assert "<i>Rossi</i>" not in catturato["corpo"]
    assert "&lt;i&gt;Rossi&lt;/i&gt;" in catturato["corpo"]


# --- Sonda dell'healthcheck Gmail -------------------------------------
# Fino al 2026-09-04 verifica_credenziali_gmail() interrogava
# users.getProfile(): una lettura, mentre lo scope concesso è gmail.send.
# Con credenziali sane rispondeva 403 e l'healthcheck dichiarava fermo un
# invio email che funzionava. Questi test fissano le due proprietà che il
# fix garantisce: la sonda è il refresh del token, e non tocca l'API Gmail.

class CredenzialiFinte:
    def __init__(self, esito_refresh=None):
        self.token = None
        self._esito_refresh = esito_refresh

    def refresh(self, request):
        if self._esito_refresh is not None:
            raise self._esito_refresh
        self.token = "access-token-finto"


def test_healthcheck_gmail_non_interroga_lapi_gmail(monkeypatch):
    credenziali = CredenzialiFinte()
    monkeypatch.setattr(
        email_service, "credenziali_oauth_google",
        lambda refresh_token, client_id, client_secret: credenziali
    )
    # Se la sonda tornasse a costruire un client Gmail, il test fallisce qui
    # invece che in produzione con un falso allarme su Discord.
    def build_vietata(*args, **kwargs):
        raise AssertionError("la sonda non deve chiamare l'API Gmail: lo scope è gmail.send")
    monkeypatch.setattr(email_service, "build", build_vietata)

    assert email_service.verifica_credenziali_gmail() is True
    assert credenziali.token is not None


def test_healthcheck_gmail_falso_se_il_refresh_fallisce(monkeypatch):
    monkeypatch.setattr(
        email_service, "credenziali_oauth_google",
        lambda refresh_token, client_id, client_secret: CredenzialiFinte(
            esito_refresh=RuntimeError("invalid_grant: Token has been expired or revoked.")
        )
    )

    assert email_service.verifica_credenziali_gmail() is False
