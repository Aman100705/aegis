"""Prometheus metrics."""
from __future__ import annotations

from prometheus_client import Counter, Histogram

DECISIONS = Counter("aegis_decisions_total", "Risk decisions issued", ["decision"])
EVAL_LATENCY = Histogram("aegis_evaluate_seconds", "Risk evaluation latency (seconds)")
