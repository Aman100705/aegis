"""Database layer (SQLAlchemy 2.0). SQLite by default; swap DATABASE_URL for
Postgres in production. Stores an immutable audit trail of every decision."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Event(Base):
    __tablename__ = "events"
    # Composite index serves the hot path: "recent events for this user".
    __table_args__ = (Index("ix_events_user_ts", "user_token", "ts"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_token: Mapped[str] = mapped_column(String(32))
    event_type: Mapped[str] = mapped_column(String(20))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    user_token: Mapped[str] = mapped_column(String(32), index=True)
    risk_score: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(20), index=True)
    reasons: Mapped[list] = mapped_column(JSON)
    features: Mapped[dict] = mapped_column(JSON)
    # Analyst feedback for the supervised feedback loop.
    label: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


def make_engine(url: str):
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


def make_sessionmaker(engine):
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_db(engine) -> None:
    Base.metadata.create_all(engine)
