"""Explainable rule signals. Each triggered rule contributes a weighted reason
code, so every score can be explained back to a human (and an auditor)."""
from __future__ import annotations

from .types import EngineEvent, Features, Reason


def evaluate_rules(
    features: Features,
    event: EngineEvent,
    *,
    impossible_travel_kmh: float = 900.0,
    velocity_threshold: int = 5,
    zscore_threshold: float = 3.0,
    failed_login_threshold: int = 3,
) -> list[Reason]:
    reasons: list[Reason] = []

    if features.geo_velocity_kmh is not None and features.geo_velocity_kmh > impossible_travel_kmh:
        reasons.append(Reason("IMPOSSIBLE_TRAVEL", "Location change too fast to be physically possible", 60))

    if features.is_new_device:
        reasons.append(Reason("NEW_DEVICE", "Sign-in from a device not seen before", 18))

    if features.is_new_ip:
        reasons.append(Reason("NEW_IP", "Sign-in from a new network/IP", 8))

    if features.unusual_hour:
        reasons.append(Reason("UNUSUAL_HOUR", "Activity at an hour unusual for this user", 10))

    if features.events_last_5m >= velocity_threshold:
        reasons.append(Reason("HIGH_VELOCITY", "Many events in a short window", 22))

    if features.amount_zscore is not None and features.amount_zscore >= zscore_threshold:
        reasons.append(Reason("AMOUNT_ANOMALY", "Transaction far larger than this user's norm", 30))

    if features.is_large_amount:
        reasons.append(Reason("LARGE_AMOUNT", "High-value transaction", 15))

    if features.failed_attempts >= failed_login_threshold:
        reasons.append(Reason("FAILED_LOGINS", "Repeated failed sign-in attempts", 20))

    return reasons
