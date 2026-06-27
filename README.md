# Aegis — Adaptive Account-Takeover &amp; Transaction-Risk Engine

[![CI](https://github.com/Aman100705/aegis/actions/workflows/ci.yml/badge.svg)](https://github.com/Aman100705/aegis/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB.svg)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> Every login and payment gets a **proportional verdict** — `allow` · `step_up` · `review` · `block` — with the **reasons why**, in milliseconds.

Most fraud systems still decide "block or allow." In digital banking that's the wrong shape: you're rarely certain enough to lock a real customer out, but "allow" leaves the door open. **Aegis** issues a *graduated* response and explains every decision, so a suspicious sign-in can be challenged with step-up auth instead of blocked, and a genuinely dangerous one is stopped — each with an auditable reason.

It's built as a self-contained Python service that a bank or a fintech could drop in behind their digital-banking platform (think a Q2 Innovation-Studio–style extension).

## How it decides

```
event ──► features ──► rule signals (explainable) ─┐
                   └──► ML anomaly (IsolationForest) ┴─► risk score 0–100 ──► proportional policy ──► verdict + reasons
```

- **Rules** are the explainable backbone — impossible travel (geo-velocity), new device/IP, unusual hour, transaction-amount anomaly (z-score vs the user's own history), velocity bursts, repeated failed logins. Each contributes a weighted **reason code**.
- **ML** (scikit-learn `IsolationForest`) catches odd *combinations* the rules don't enumerate, and augments — never overrides — the explainable score.
- **Policy** maps the score to a proportional decision, with a hard floor so impossible travel is never silently allowed.

Example: a clean Delhi login scores **5 → allow**; the same user appearing in London five minutes later on a new device scores **100 → block** with reasons `IMPOSSIBLE_TRAVEL, ML_ANOMALY, FAILED_LOGINS, NEW_DEVICE, NEW_IP`.

## Run it

```bash
pip install -e ".[dev]"          # or: pip install fastapi "uvicorn[standard]" pydantic pydantic-settings SQLAlchemy scikit-learn numpy prometheus-client
uvicorn aegis.main:app --reload  # http://localhost:8000
```

- **Analyst console:** http://localhost:8000/ — evaluate events, watch the review queue, confirm fraud / dismiss false positives.
- **API docs (OpenAPI):** http://localhost:8000/docs
- **Generate demo traffic:** `python scripts/simulate.py --url http://localhost:8000 --key demo-key --n 200`

### Docker

```bash
docker compose up --build        # aegis on :8000 (+ provisioned postgres)
```

## API

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/risk/evaluate` | Score an event → proportional decision + reasons |
| GET | `/v1/review-queue` | Decisions flagged for analyst review |
| POST | `/v1/decisions/{id}/resolve` | Analyst feedback (`confirmed_fraud` / `false_positive`) |
| GET | `/v1/stats` | Decision counts + pending review |
| GET | `/healthz` · `/readyz` · `/metrics` | Probes + Prometheus metrics |

Authenticate with `X-API-Key` (configured via `AEGIS_API_KEYS`; open in dev with a startup warning).

## Security &amp; privacy

- **PII tokenization** — user identifiers are HMAC-SHA256 tokenized before they touch the database or logs: deterministic (history stays queryable) but non-reversible.
- **Immutable audit trail** — every decision is persisted with its feature snapshot and reasons.
- **Input validation** (Pydantic), **timing-safe API-key auth** (`hmac.compare_digest`), **rate limiting** (429 + `retry-after`), **security headers** (nosniff / frame-options / referrer), **request-id correlation**, structured JSON logging, non-root container.
- Analyst resolutions are captured as labels — the supervised signal for retraining the model (feedback loop).

## Tech &amp; layout

Python · FastAPI · Pydantic v2 · SQLAlchemy 2 (SQLite default, Postgres-ready via `AEGIS_DATABASE_URL`) · scikit-learn · Prometheus · pytest · ruff · Docker.

```
aegis/
├── engine/        # pure, tested risk logic — the core
│   ├── features.py  # geo-velocity, anomalies, velocity
│   ├── rules.py     # explainable reason codes + weights
│   ├── anomaly.py   # IsolationForest wrapper
│   └── policy.py    # score blend + proportional decision
├── service.py     # tokenize → score → persist audit trail → feedback
├── repository.py  # data access (history, review queue, stats)
├── api/routes.py  # FastAPI endpoints
├── db.py models.py schemas.py security.py config.py metrics.py
static/            # analyst console (served at /)
scripts/simulate.py
tests/             # engine + API tests
```

## Testing

```bash
pytest -q        # 23 engine / API / security tests
ruff check .     # lint
mypy aegis       # static type-check (clean)
```

A full production-readiness review is in [`docs/AUDIT.md`](docs/AUDIT.md).

## License

MIT — see [LICENSE](LICENSE).
