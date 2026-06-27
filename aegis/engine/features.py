"""Feature extraction. Turns a raw event plus the user's history into the
numeric signals the rules and ML model consume."""
from __future__ import annotations

import math

from .types import EngineEvent, Features, History


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in kilometers."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def compute_features(event: EngineEvent, history: History, large_amount: float) -> Features:
    minutes_since_last: float | None = None
    if history.prev_ts is not None:
        minutes_since_last = (event.ts - history.prev_ts).total_seconds() / 60.0

    geo_velocity: float | None = None
    if (
        event.lat is not None
        and event.lon is not None
        and history.prev_lat is not None
        and history.prev_lon is not None
        and minutes_since_last is not None
        and minutes_since_last >= 0
    ):
        dist = haversine_km(history.prev_lat, history.prev_lon, event.lat, event.lon)
        hours = max(minutes_since_last / 60.0, 1.0 / 3600.0)  # floor at 1 second
        geo_velocity = dist / hours

    seen_before = history.event_count > 0
    is_new_device = bool(seen_before and event.device_id and event.device_id not in history.known_devices)
    is_new_ip = bool(seen_before and event.ip and event.ip not in history.known_ips)

    unusual_hour = bool(
        history.event_count >= 5 and history.typical_hours and event.ts.hour not in history.typical_hours
    )

    amount_zscore: float | None = None
    if event.amount is not None and history.amount_mean is not None and history.amount_std:
        amount_zscore = (event.amount - history.amount_mean) / history.amount_std

    is_large_amount = bool(event.amount is not None and event.amount >= large_amount)

    return Features(
        minutes_since_last=minutes_since_last,
        geo_velocity_kmh=geo_velocity,
        is_new_device=is_new_device,
        is_new_ip=is_new_ip,
        unusual_hour=unusual_hour,
        amount_zscore=amount_zscore,
        events_last_5m=history.events_last_5m,
        failed_attempts=event.failed_attempts,
        is_large_amount=is_large_amount,
    )
