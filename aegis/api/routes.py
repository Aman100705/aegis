"""HTTP routes. Thin transport over the service layer."""
from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..schemas import DecisionOut, EventIn, ResolveIn, ReviewItem, StatsOut
from ..security import require_api_key
from ..service import RiskService

router = APIRouter()


def get_session(request: Request) -> Iterator[Session]:
    maker = request.app.state.sessionmaker
    db = maker()
    try:
        yield db
    finally:
        db.close()


def get_service(request: Request, db: Session = Depends(get_session)) -> RiskService:
    return RiskService(db, request.app.state.model, request.app.state.settings)


@router.post("/risk/evaluate", response_model=DecisionOut, dependencies=[Depends(require_api_key)])
def evaluate(payload: EventIn, service: RiskService = Depends(get_service)) -> DecisionOut:
    return service.evaluate(payload)


@router.get("/review-queue", response_model=list[ReviewItem], dependencies=[Depends(require_api_key)])
def review_queue(
    service: RiskService = Depends(get_service),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[ReviewItem]:
    return [
        ReviewItem(
            decision_id=d.id, user_token=d.user_token, risk_score=d.risk_score,
            decision=d.decision, reasons=d.reasons, created_at=d.created_at,
        )
        for d in service.repo.review_queue(limit=limit, offset=offset)
    ]


@router.post("/decisions/{decision_id}/resolve", dependencies=[Depends(require_api_key)])
def resolve(decision_id: str, body: ResolveIn, service: RiskService = Depends(get_service)) -> dict:
    decision = service.resolve(decision_id, body.label)
    if decision is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    return {"decision_id": decision.id, "label": decision.label}


@router.get("/stats", response_model=StatsOut, dependencies=[Depends(require_api_key)])
def stats(service: RiskService = Depends(get_service)) -> StatsOut:
    return StatsOut(decisions=service.repo.decision_counts(), pending_review=service.repo.pending_review_count())
