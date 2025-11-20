from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_apitest_endpoint_returns_ok():
    resp = client.get("/api/v1/apitest")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ok"
    assert "timestamp" in data
    assert "app_name" in data
    assert "db" in data
    assert isinstance(data["db"].get("connected"), bool)
