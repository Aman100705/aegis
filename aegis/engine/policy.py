"""Policy + orchestration. Combines rule weights with the ML anomaly score into
a 0-100 risk score, then maps it to a *proportional* decision:
allow -> step_up -> review -> block. This is the core thesis: not 'block or
allow', but a graduated, explainable response."""
from __future__ import annotations

from dataclasses import dataclass

from .anomaly import AnomalyModel
from .features import compute_features
from .rules import evaluate_rules
from .types import EngineEvent, History, Reason, RiskResult


@dataclass
class PolicyConfig:
    score_step_up: int = 20
    score_review: int = 45
    score_block: int = 70
    impossible_travel_kmh: float = 900.0
    velocity_threshold: int = 5
    large_amount: float = 100_000.0
    ml_max_contribution: int = 30


SEVERITY = {"allow": 0, "step_up": 1, "review": 2, "block": 3}


def decide(score: int, reasons: list[Reason], cfg: PolicyConfig) -> str:
    if score >= cfg.score_block:
        decision = "block"
    elif score >= cfg.score_review:
        decision = "review"
    elif score >= cfg.score_step_up:
        decision = "step_up"
    else:
        decision = "allow"

    # Hard floor: impossible travel should never be silently allowed.
    codes = {r.code for r in reasons}
    if "IMPOSSIBLE_TRAVEL" in codes and SEVERITY[decision] < SEVERITY["step_up"]:
        decision = "step_up"
    return decision


def score_event(
    event: EngineEvent,
    history: History,
    model: AnomalyModel | None,
    cfg: PolicyConfig,
) -> RiskResult:
    features = compute_features(event, history, cfg.large_amount)
    reasons = evaluate_rules(
        features,
        event,
        impossible_travel_kmh=cfg.impossible_travel_kmh,
        velocity_threshold=cfg.velocity_threshold,
    )

    rule_score = sum(r.weight for r in reasons)

    ml_contribution = 0
    if model is not None:
        anomaly = model.anomaly_score(features)
        ml_contribution = int(round(anomaly * cfg.ml_max_contribution))
        if ml_contribution >= 10:
            reasons.append(Reason("ML_ANOMALY", "Unusual combination of signals (model)", ml_contribution))

    risk_score = int(min(100, rule_score + ml_contribution))
    decision = decide(risk_score, reasons, cfg)
    reasons.sort(key=lambda r: r.weight, reverse=True)
    return RiskResult(risk_score=risk_score, decision=decision, reasons=reasons, features=features)
