"""API smoke tests."""

from fastapi.testclient import TestClient

from aegis.api.main import app


client = TestClient(app)


def test_healthz():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_run_evaluation():
    resp = client.post("/v1/evaluations", json={"dataset": "smoke", "persist": False})
    assert resp.status_code == 200
    body = resp.json()
    assert "run_id" in body
    assert body["metrics"]["overall"] > 0
    assert body["governance"]["deploy_allowed"] is True


def test_adversarial_endpoint():
    resp = client.post("/v1/adversarial")
    assert resp.status_code == 200
    body = resp.json()
    assert "pass_rates" in body
