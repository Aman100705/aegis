"""Cross-cutting middleware: request correlation id, security headers, and a
dependency-free fixed-window rate limiter (keyed by API key, else client IP).

The rate limiter is in-memory and therefore per-instance; for multi-instance
deployments back it with Redis. It is intentionally simple and allocation-light
so it adds negligible latency to the hot path."""
from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse, Response


class FixedWindowRateLimiter:
    def __init__(self, limit_per_minute: int) -> None:
        self.limit = limit_per_minute
        self._buckets: dict[tuple[str, int], int] = {}

    def hit(self, key: str) -> tuple[bool, int]:
        """Return (allowed, remaining). limit<=0 disables limiting."""
        if self.limit <= 0:
            return True, 0
        window = int(time.time() // 60)
        bkey = (key, window)
        count = self._buckets.get(bkey, 0) + 1
        self._buckets[bkey] = count
        if len(self._buckets) > 50_000:  # opportunistic cleanup of old windows
            self._buckets = {k: v for k, v in self._buckets.items() if k[1] >= window}
        return count <= self.limit, max(0, self.limit - count)


def install_middleware(app: FastAPI, *, rate_limit_per_minute: int) -> None:
    limiter = FixedWindowRateLimiter(rate_limit_per_minute)

    @app.middleware("http")
    async def correlate_and_protect(request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex

        if request.url.path.startswith("/v1"):
            client = request.headers.get("x-api-key") or (request.client.host if request.client else "anon")
            allowed, remaining = limiter.hit(client)
            if not allowed:
                return JSONResponse(
                    {"detail": "Rate limit exceeded", "request_id": request_id},
                    status_code=429,
                    headers={"x-request-id": request_id, "retry-after": "60"},
                )

        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["x-frame-options"] = "DENY"
        response.headers["referrer-policy"] = "no-referrer"
        return response
