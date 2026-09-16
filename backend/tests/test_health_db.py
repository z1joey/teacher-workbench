"""Health endpoint must reflect database availability (deploy gate)."""


def test_health_ok_when_database_reachable(client):
    r = client.get("/api/health")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert "version" in body


def test_health_503_when_database_unreachable(client, monkeypatch):
    from app import main as main_module

    class BrokenEngine:
        def connect(self):
            raise OSError("database down")

    monkeypatch.setattr(main_module, "engine", BrokenEngine())
    r = client.get("/api/health")
    assert r.status_code == 503, r.text
    assert r.json()["detail"] == "database unavailable"
