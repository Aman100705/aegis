"""Core engine types. Pure data structures with no I/O, so the risk logic is
fully unit-testable and could run in a worker, a stream processor, or inline."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EngineEvent:
    """A normalized auth or payment event to be scored."""

    user_token: str
    event_type: str  # "login" | "transaction"
    ts: datetime
    ip: str | None = None
    device_id: str | None = None
    lat: float | None = None
    lon: float | None = None
    amount: float | None = None
    mfa_passed: bool | None = None
    failed_attempts: int = 0


@dataclass
class History:
    """Summary of the user's prior behavior, assembled by the service layer."""

    event_count: int = 0
    prev_ts: datetime | None = None
    prev_lat: float | None = None
    prev_lon: float | None = None
    known_devices: set[str] = field(default_factory=set)
    known_ips: set[str] = field(default_factory=set)
    amount_mean: float | None = None
    amount_std: float | None = None
    events_last_5m: int = 0
    typical_hours: set[int] = field(default_factory=set)


@dataclass
class Features:
    minutes_since_last: float | None
    geo_velocity_kmh: float | None
    is_new_device: bool
    is_new_ip: bool
    unusual_hour: bool
    amount_zscore: float | None
    events_last_5m: int
    failed_attempts: int
    is_large_amount: bool

    def vector(self) -> list[float]:
        """Numeric feature vector for the anomaly model."""
        return [
            min(self.geo_velocity_kmh or 0.0, 5000.0) / 5000.0,
            1.0 if self.is_new_device else 0.0,
            1.0 if self.is_new_ip else 0.0,
            1.0 if self.unusual_hour else 0.0,
            min(abs(self.amount_zscore or 0.0), 10.0) / 10.0,
            min(self.events_last_5m, 20) / 20.0,
            min(self.failed_attempts, 10) / 10.0,
        ]


@dataclass
class Reason:
    code: str
    label: str
    weight: int


@dataclass
class RiskResult:
    risk_score: int
    decision: str  # allow | step_up | review | block
    reasons: list[Reason]
    features: Features
