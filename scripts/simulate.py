"""Synthetic event generator. Streams realistic traffic at a running Aegis
instance: mostly normal behavior plus injected fraud scenarios (impossible
travel, takeover bursts, anomalous transfers).

    python scripts/simulate.py --url http://localhost:8000 --key demo --n 200
"""
from __future__ import annotations

import argparse
import random
import time
from datetime import UTC, datetime, timedelta

import httpx

CITIES = {
    "delhi": (28.61, 77.21),
    "mumbai": (19.07, 72.88),
    "london": (51.50, -0.12),
    "austin": (30.27, -97.74),
}
USERS = [f"user{i:03d}" for i in range(1, 21)]


def normal_event(user: str, ts: datetime) -> dict:
    lat, lon = CITIES["delhi"]
    return {
        "user_id": user, "event_type": random.choice(["login", "transaction"]),
        "ip": "1.1.1.1", "device_id": f"{user}-phone",
        "lat": lat + random.uniform(-0.05, 0.05), "lon": lon + random.uniform(-0.05, 0.05),
        "amount": round(random.uniform(200, 3000), 2), "failed_attempts": 0,
        "timestamp": ts.isoformat(),
    }


def fraud_event(user: str, ts: datetime) -> dict:
    lat, lon = CITIES["london"]
    return {
        "user_id": user, "event_type": "login", "ip": "9.9.9.9", "device_id": "attacker-device",
        "lat": lat, "lon": lon, "failed_attempts": random.randint(3, 6),
        "timestamp": ts.isoformat(),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--key", default="")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--fraud-rate", type=float, default=0.05)
    args = ap.parse_args()

    headers = {"X-API-Key": args.key} if args.key else {}
    ts = datetime.now(UTC) - timedelta(hours=2)
    counts: dict[str, int] = {}

    with httpx.Client(base_url=args.url, headers=headers, timeout=10) as client:
        for _ in range(args.n):
            user = random.choice(USERS)
            ts += timedelta(seconds=random.randint(20, 120))
            event = fraud_event(user, ts) if random.random() < args.fraud_rate else normal_event(user, ts)
            r = client.post("/v1/risk/evaluate", json=event)
            if r.status_code == 200:
                d = r.json()["decision"]
                counts[d] = counts.get(d, 0) + 1
            time.sleep(0.005)

    print("Decisions:", counts)


if __name__ == "__main__":
    main()
