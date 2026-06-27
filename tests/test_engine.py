"""Engine unit tests — pure, fast, no I/O."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aegis.engine.features import compute_features, haversine_km
from aegis.engine.policy import PolicyConfig, decide, score_event
from aegis.engine.rules import evaluate_rules
from aegis.engine.types import EngineEvent, History, Reason

CFG = PolicyConfig()
NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def login(**kw) -> EngineEvent:
    base = dict(user_token="u1", event_type="login", ts=NOW)
    base.update(kw)
    return EngineEvent(**base)


def test_haversine_known_distance():
    # Delhi -> Mumbai is ~1150 km.
    d = haversine_km(28.61, 77.21, 19.07, 72.88)
    assert 1100 < d < 1200


def test_impossible_travel_detected():
    hist = History(event_count=3, prev_ts=NOW - timedelta(minutes=10), prev_lat=28.61, prev_lon=77.21,
                   known_devices={"d1"}, known_ips={"1.1.1.1"}, typical_hours={12})
    ev = login(ts=NOW, lat=19.07, lon=72.88, device_id="d1", ip="1.1.1.1")
    feats = compute_features(ev, hist, CFG.large_amount)
    assert feats.geo_velocity_kmh is not None and feats.geo_velocity_kmh > 900
    reasons = evaluate_rules(feats, ev)
    assert any(r.code == "IMPOSSIBLE_TRAVEL" for r in reasons)


def test_new_device_flagged_only_when_history_exists():
    hist = History(event_count=5, known_devices={"known"}, typical_hours={12})
    feats = compute_features(login(device_id="brand-new"), hist, CFG.large_amount)
    assert feats.is_new_device is True
    # First-ever event: no history, so not "new".
    feats0 = compute_features(login(device_id="brand-new"), History(), CFG.large_amount)
    assert feats0.is_new_device is False


def test_amount_zscore_anomaly():
    hist = History(event_count=10, amount_mean=1000.0, amount_std=200.0, typical_hours={12})
    ev = EngineEvent(user_token="u1", event_type="transaction", ts=NOW, amount=5000.0)
    feats = compute_features(ev, hist, CFG.large_amount)
    assert feats.amount_zscore is not None and feats.amount_zscore >= 3
    assert any(r.code == "AMOUNT_ANOMALY" for r in evaluate_rules(feats, ev))


def test_proportional_decisions_by_score():
    assert decide(5, [], CFG) == "allow"
    assert decide(25, [], CFG) == "step_up"
    assert decide(50, [], CFG) == "review"
    assert decide(80, [], CFG) == "block"


def test_impossible_travel_never_silently_allowed():
    # Low score but impossible travel present -> at least step_up.
    reasons = [Reason("IMPOSSIBLE_TRAVEL", "x", 60)]
    assert decide(0, reasons, CFG) == "step_up"


def test_clean_event_allows():
    hist = History(event_count=10, prev_ts=NOW - timedelta(hours=2), prev_lat=28.6, prev_lon=77.2,
                   known_devices={"d1"}, known_ips={"1.1.1.1"}, typical_hours={12})
    ev = login(device_id="d1", ip="1.1.1.1", lat=28.6, lon=77.2)
    result = score_event(ev, hist, None, CFG)
    assert result.decision == "allow"
    assert result.risk_score < CFG.score_step_up


def test_high_risk_blocks():
    hist = History(event_count=5, prev_ts=NOW - timedelta(minutes=2), prev_lat=28.6, prev_lon=77.2,
                   known_devices={"d1"}, known_ips={"1.1.1.1"}, events_last_5m=6, typical_hours={3})
    ev = login(ts=NOW, lat=51.5, lon=-0.12, device_id="new", ip="9.9.9.9", failed_attempts=4)
    result = score_event(ev, hist, None, CFG)
    assert result.decision in ("review", "block")
    assert result.risk_score >= CFG.score_review
