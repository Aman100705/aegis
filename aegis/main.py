"""Application factory + composition root."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .api.routes import router
from .config import Settings, get_settings
from .db import init_db, make_engine, make_sessionmaker
from .engine.anomaly import AnomalyModel
from .logging import configure_logging
from .middleware import install_middleware

log = logging.getLogger("aegis")


def create_app(settings: Settings | None = None, engine=None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    engine = engine or make_engine(settings.database_url)
    init_db(engine)

    app = FastAPI(
        title="Aegis Risk Engine",
        version="0.1.0",
        description=(
            "Adaptive account-takeover & transaction-risk decisioning with "
            "proportional, explainable responses."
        ),
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = make_sessionmaker(engine)
    app.state.model = AnomalyModel.train_default()

    # Startup safety warnings (fail loud, not silent).
    if not settings.api_key_list:
        log.warning("AEGIS_API_KEYS is empty — API is OPEN. Set keys before production.")
    if settings.pii_secret == "dev-insecure-change-me":
        log.warning("AEGIS_PII_SECRET is the insecure default — set a real secret before production.")

    install_middleware(app, rate_limit_per_minute=settings.rate_limit_per_minute)
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        rid = request.headers.get("x-request-id", "-")
        log.exception("unhandled error", extra={"extra_fields": {"request_id": rid}})
        return JSONResponse({"detail": "Internal server error", "request_id": rid}, status_code=500)

    app.include_router(router, prefix="/v1")

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    def readyz() -> dict:
        return {"status": "ready", "model": app.state.model is not None}

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> PlainTextResponse:
        return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    static_dir = Path(__file__).resolve().parent.parent / "static"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


app = create_app()
