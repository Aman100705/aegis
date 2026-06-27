"""Security, ML, and middleware tests."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from aegis.config import Settings
from aegis.engine.anomaly import AnomalyModel
from aegis.engine.types import Features
from aegis.main import create_app
from aegis.security import key_is_valid, tokenize


def test_tokenize_is_deterministic_and_irreversible():
    a = tokenize("user-123", "secret")
    b = tokenize("user-123", "secret")
    assert a == b                      # deterministic => history is queryable
    assert "user-123" not in a         # raw id not present
    assert tokenize("user-123", "other") != a  # secret-dependent
    assert len(a) == 32


def test_key_is_valid_constant_time_membership():
    assert key_is_valid("k2", ["k1", "k2"]) is True
    assert key_is_valid("nope", ["k1", "k2"]) is False


def test_anomaly_model_scores_in_range_and_flags_outliers():
    model = AnomalyModel.train_default(seed=1)
    normal = Features(0.0, 10.0, False, False, False, 0.0, 0, 0, False)
    weird = Features(0.0, 4000.0, True, True, True, 8.0, 15, 8, True)
    s_normal = model.anomaly_score(normal)
    s_weird = model.anomaly_score(weird)
    assert 0.0 <= s_normal <= 1.0 and 0.0 <= s_weird <= 1.0
    assert s_weird > s_normal


def _client(**overrides) -> TestClient:
    settings = Settings(database_url="sqlite://", api_keys="k", pii_secret="t", **overrides)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    return TestClient(create_app(settings=settings, engine=engine))


def test_security_headers_and_request_id_present():
    c = _client()
    r = c.get("/v1/stats", headers={"X-API-Key": "k"})
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("x-request-id")


def test_rate_limit_returns_429_when_exceeded():
    c = _client(rate_limit_per_minute=3)
    h = {"X-API-Key": "k"}
    codes = [c.get("/v1/stats", headers=h).status_code for _ in range(5)]
    assert 429 in codes
    assert codes.count(200) == 3


def test_review_queue_pagination_param_validation():
    c = _client()
    r = c.get("/v1/review-queue", params={"limit": 0}, headers={"X-API-Key": "k"})
    assert r.status_code == 422  # limit must be >= 1


def test_resolve_unknown_decision_404():
    c = _client()
    r = c.post("/v1/decisions/does-not-exist/resolve", json={"label": "false_positive"}, headers={"X-API-Key": "k"})
    assert r.status_code == 404


@pytest.mark.parametrize("label", ["confirmed_fraud", "false_positive"])
def test_resolve_label_validation(label: str):
    c = _client()
    # invalid label rejected by schema
    bad = c.post("/v1/decisions/x/resolve", json={"label": "maybe"}, headers={"X-API-Key": "k"})
    assert bad.status_code == 422
