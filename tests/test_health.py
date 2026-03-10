def test_health_returns_200(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert data["service"] == "translator"
    assert data["version"] == "1.0.0"
    assert "checks" in data
    assert "argos_translate" in data["checks"]
    assert "models_volume" in data["checks"]
