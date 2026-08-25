# Copre GET /health (backend/main.py) — l'endpoint che un servizio di
# monitoraggio esterno (UptimeRobot o simili) interroga periodicamente per
# sapere se il sito è raggiungibile E se il database risponde ancora.

def test_health_risponde_ok(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
