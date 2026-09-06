# Copre /health (backend/main.py) — l'endpoint che un servizio di
# monitoraggio esterno (UptimeRobot, e il workflow .github/workflows/
# monitor.yml) interroga periodicamente per sapere se il sito è
# raggiungibile E se il database risponde ancora.
#
# HEAD è coperto quanto GET, e non per completezza formale: i servizi di
# uptime usano HEAD di default, perché scaricare il corpo per sapere se un
# sito risponde è sprecato. Il 2026-09-07 nei log di produzione è comparso
# `"HEAD /health HTTP/1.1" 405 Method Not Allowed` — la rotta dichiarava
# solo GET, e il monitor appena configurato riceveva un errore da un
# servizio perfettamente sano. Un endpoint di monitoraggio che risponde
# male proprio a chi lo monitora è il caso peggiore: fa sembrare rotto
# quello che funziona, e il primo istinto è andare a cercare il guasto
# nella parte sbagliata.

import pytest
from sqlalchemy.exc import OperationalError

from backend.database import get_db
from backend.main import app


def test_health_risponde_ok(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_health_risponde_anche_a_head(client):
    """HEAD deve dare lo stesso esito di GET, con il corpo vuoto: è così
    che lo interroga un servizio di uptime."""
    res = client.head("/health")

    assert res.status_code == 200
    # Il corpo di una risposta a HEAD è vuoto per definizione del protocollo:
    # il server lo scarta. Ciò che conta per il monitor è il codice.
    assert res.content == b""


class SessioneRotta:
    """Una sessione che si apre ma esplode alla prima query.

    La differenza rispetto a far fallire direttamente la dependency non è
    sottile: FastAPI risolve le dependency **prima** di chiamare la
    funzione dell'endpoint, quindi una dependency che esplode fa fallire la
    richiesta anche se l'endpoint il database non lo tocca affatto. Un test
    scritto così passerebbe anche con il controllo sul database rimosso —
    verificato con una mutazione, ed è esattamente quello che è successo
    alla prima stesura di questo file.
    """

    def execute(self, *args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("database irraggiungibile"))

    def close(self):
        pass


@pytest.fixture
def database_irraggiungibile():
    """Sostituisce la sessione con una che esplode alla prima query, per
    simulare il database giù senza doverlo spegnere davvero."""
    def db_rotto():
        yield SessioneRotta()

    app.dependency_overrides[get_db] = db_rotto
    yield
    # Ripristina l'override normale della suite (vedi tests/conftest.py):
    # senza, tutti i test successivi troverebbero il database rotto.
    from conftest import _override_get_db
    app.dependency_overrides[get_db] = _override_get_db


def test_health_fallisce_se_il_database_non_risponde(client, database_irraggiungibile):
    """È la ragione per cui questo endpoint esiste invece di rispondere
    sempre 200: un processo vivo con il database irraggiungibile è comunque
    un servizio fuori uso, e il monitor deve accorgersene."""
    with pytest.raises(OperationalError):
        client.get("/health")


def test_head_interroga_davvero_il_database(client, database_irraggiungibile):
    """Il controllo che conta davvero su HEAD: siccome il corpo viene
    scartato, una risposta che non toccasse il database darebbe comunque
    200 e il monitor direbbe "tutto bene" con il database giù."""
    with pytest.raises(OperationalError):
        client.head("/health")
