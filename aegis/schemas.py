"""API contract (Pydantic v2). FastAPI uses these for validation and to generate
the OpenAPI spec served at /docs."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class EventIn(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    event_type: Literal["login", "transaction"]
    timestamp: datetime | None = None
    ip: str | None = Field(default=None, max_length=64)
    device_id: str | None = Field(default=None, max_length=64)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    amount: float | None = Field(default=None, ge=0)
    mfa_passed: bool | None = None
    failed_attempts: int = Field(default=0, ge=0, le=1000)


class ReasonOut(BaseModel):
    code: str
    label: str
    weight: int


class DecisionOut(BaseModel):
    decision_id: str
    event_id: str
    decision: Literal["allow", "step_up", "review", "block"]
    risk_score: int
    reasons: list[ReasonOut]
    evaluated_at: datetime


class ReviewItem(BaseModel):
    decision_id: str
    user_token: str
    risk_score: int
    decision: str
    reasons: list[ReasonOut]
    created_at: datetime


class ResolveIn(BaseModel):
    label: Literal["confirmed_fraud", "false_positive"]


class StatsOut(BaseModel):
    decisions: dict[str, int]
    pending_review: int
