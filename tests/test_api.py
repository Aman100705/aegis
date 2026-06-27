"""API integration tests against an in-memory database."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from aegis.config import Settings
from aegis.main import create_app


@pytest.fixture
def client() -> TestClient:
    settings = Settings(database_url="sqlite://", api_keys="test-key", pii_secret="t")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    app = create_app(settings=settings, engine=engine)
    return TestClient(app)


AUTH = {"X-API-Key": "test-key"}


def test_health(client: TestClient):
    assert client.get("/healthz").json()["status"] == "ok"


def test_requires_api_key(client: TestClient):
    r = client.post("/v1/risk/evaluate", json={"user_id": "u1", "event_type": "login"})
    assert r.status_code == 401


def test_evaluate_clean_then_takeover(client: TestClient):
    # Establish a baseline in Delhi on a known device.
    base = {"user_id": "alice", "event_type": "login", "ip": "1.1.1.1", "device_id": "phone",
            "lat": 28.61, "lon": 77.21, "timestamp": "2026-06-01T08:00:00Z"}
    r1 = client.post("/v1/risk/evaluate", json=base, headers=AUTH)
    assert r1.status_code == 200
    assert r1.json()["decision"] == "allow"

    # Minutes later, sign-in from London on a new device => impossible travel.
    takeover = {"user_id": "alice", "event_type": "login", "ip": "9.9.9.9", "device_id": "unknown",
                "lat": 51.50, "lon": -0.12, "timestamp": "2026-06-01T08:05:00Z", "failed_attempts": 3}
    r2 = client.post("/v1/risk/evaluate", json=takeover, headers=AUTH)
    body = r2.json()
    assert body["decision"] in ("review", "block")
    codes = {x["code"] for x in body["reasons"]}
    assert "IMPOSSIBLE_TRAVEL" in codes


def test_review_queue_and_resolve(client: TestClient):
    takeover = {"user_id": "bob", "event_type": "login", "ip": "9.9.9.9", "device_id": "x",
                "lat": 51.5, "lon": -0.12, "timestamp": "2026-06-01T08:00:00Z"}
    # Seed a prior far-away event so the next one trips impossible travel.
    client.post("/v1/risk/evaluate", json={**takeover, "lat": 28.6, "lon": 77.2,
                                           "timestamp": "2026-06-01T07:58:00Z"}, headers=AUTH)
    client.post("/v1/risk/evaluate", json=takeover, headers=AUTH)

    q = client.get("/v1/review-queue", headers=AUTH).json()
    assert len(q) >= 1
    did = q[0]["decision_id"]

    resolved = client.post(f"/v1/decisions/{did}/resolve", json={"label": "confirmed_fraud"}, headers=AUTH)
    assert resolved.status_code == 200
    assert resolved.json()["label"] == "confirmed_fraud"


def test_validation_rejects_bad_event(client: TestClient):
    r = client.post("/v1/risk/evaluate", json={"user_id": "u", "event_type": "nonsense"}, headers=AUTH)
    assert r.status_code == 422


def test_stats(client: TestClient):
    client.post("/v1/risk/evaluate", json={"user_id": "c", "event_type": "login"}, headers=AUTH)
    s = client.get("/v1/stats", headers=AUTH).json()
    assert "decisions" in s and "pending_review" in s
