"""Data access. Keeps SQL out of the service/engine so they stay testable."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from statistics import pstdev

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import Decision, Event
from .engine.types import History


class Repository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def add_event(self, **kwargs) -> Event:
        ev = Event(**kwargs)
        self.s.add(ev)
        self.s.flush()
        return ev

    def add_decision(self, **kwargs) -> Decision:
        d = Decision(**kwargs)
        self.s.add(d)
        self.s.flush()
        return d

    def build_history(self, user_token: str, now: datetime, lookback: int = 500) -> History:
        rows = list(
            self.s.execute(
                select(Event)
                .where(Event.user_token == user_token)
                .order_by(Event.ts.desc())
                .limit(lookback)
            ).scalars()
        )
        if not rows:
            return History()

        prev = rows[0]  # most recent prior event
        amounts = [r.amount for r in rows if r.amount is not None]
        mean = sum(amounts) / len(amounts) if amounts else None
        std = pstdev(amounts) if len(amounts) >= 2 else None
        cutoff = now - timedelta(minutes=5)

        return History(
            event_count=len(rows),
            prev_ts=_aware(prev.ts),
            prev_lat=prev.lat,
            prev_lon=prev.lon,
            known_devices={r.device_id for r in rows if r.device_id},
            known_ips={r.ip for r in rows if r.ip},
            amount_mean=mean,
            amount_std=std,
            events_last_5m=sum(1 for r in rows if _aware(r.ts) >= cutoff),
            typical_hours={r.ts.hour for r in rows},
        )

    def review_queue(self, limit: int = 50, offset: int = 0) -> list[Decision]:
        return list(
            self.s.execute(
                select(Decision)
                .where(Decision.decision.in_(["review", "block"]), Decision.label.is_(None))
                .order_by(Decision.created_at.desc())
                .limit(limit)
                .offset(offset)
            ).scalars()
        )

    def get_decision(self, decision_id: str) -> Decision | None:
        return self.s.get(Decision, decision_id)

    def decision_counts(self) -> dict[str, int]:
        rows = self.s.execute(select(Decision.decision, func.count()).group_by(Decision.decision)).all()
        return {d: n for d, n in rows}

    def pending_review_count(self) -> int:
        return int(
            self.s.execute(
                select(func.count()).select_from(Decision).where(
                    Decision.decision.in_(["review", "block"]), Decision.label.is_(None)
                )
            ).scalar_one()
        )


def _aware(ts: datetime) -> datetime:
    """SQLite may return naive datetimes; treat them as UTC for comparison."""
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)
