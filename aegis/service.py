"""Service layer. Ties the engine to persistence and security: tokenizes the
user id, assembles history, scores the event, and writes an immutable decision
to the audit trail."""
from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from .config import Settings
from .db import Decision
from .engine.anomaly import AnomalyModel
from .engine.policy import PolicyConfig, score_event
from .engine.types import EngineEvent
from .metrics import DECISIONS, EVAL_LATENCY
from .repository import Repository
from .schemas import DecisionOut, EventIn, ReasonOut
from .security import tokenize


class RiskService:
    def __init__(self, session: Session, model: AnomalyModel | None, settings: Settings) -> None:
        self.repo = Repository(session)
        self.session = session
        self.model = model
        self.settings = settings
        self.cfg = PolicyConfig(
            score_step_up=settings.score_step_up,
            score_review=settings.score_review,
            score_block=settings.score_block,
            impossible_travel_kmh=settings.impossible_travel_kmh,
            velocity_threshold=settings.velocity_threshold,
            large_amount=settings.large_amount,
        )

    @EVAL_LATENCY.time()
    def evaluate(self, payload: EventIn) -> DecisionOut:
        token = tokenize(payload.user_id, self.settings.pii_secret)
        ts = payload.timestamp or datetime.now(UTC)

        history = self.repo.build_history(token, ts)

        engine_event = EngineEvent(
            user_token=token,
            event_type=payload.event_type,
            ts=ts,
            ip=payload.ip,
            device_id=payload.device_id,
            lat=payload.lat,
            lon=payload.lon,
            amount=payload.amount,
            mfa_passed=payload.mfa_passed,
            failed_attempts=payload.failed_attempts,
        )
        result = score_event(engine_event, history, self.model, self.cfg)

        event = self.repo.add_event(
            user_token=token, event_type=payload.event_type, ts=ts,
            ip=payload.ip, device_id=payload.device_id, lat=payload.lat,
            lon=payload.lon, amount=payload.amount,
        )
        decision = self.repo.add_decision(
            event_id=event.id, user_token=token, risk_score=result.risk_score,
            decision=result.decision,
            reasons=[asdict(r) for r in result.reasons],
            features=asdict(result.features),
        )
        self.session.commit()
        DECISIONS.labels(decision=result.decision).inc()

        return DecisionOut(
            decision_id=decision.id,
            event_id=event.id,
            decision=result.decision,  # type: ignore[arg-type]
            risk_score=result.risk_score,
            reasons=[ReasonOut(**asdict(r)) for r in result.reasons],
            evaluated_at=ts,
        )

    def resolve(self, decision_id: str, label: str) -> Decision | None:
        decision = self.repo.get_decision(decision_id)
        if decision is None:
            return None
        decision.label = label
        decision.resolved_at = datetime.now(UTC)
        self.session.commit()
        return decision
