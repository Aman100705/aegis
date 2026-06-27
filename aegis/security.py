"""PII tokenization + API-key auth.

User identifiers are tokenized with HMAC-SHA256 before they touch the database
or logs: deterministic (so history is queryable) but non-reversible (so a DB
leak doesn't expose who did what)."""
from __future__ import annotations

import hashlib
import hmac

from fastapi import Header, HTTPException, Request, status


def tokenize(user_id: str, secret: str) -> str:
    return hmac.new(secret.encode(), user_id.encode(), hashlib.sha256).hexdigest()[:32]


def key_is_valid(presented: str, allowed: list[str]) -> bool:
    """Constant-time membership check to avoid leaking key bytes via timing."""
    return any(hmac.compare_digest(presented, k) for k in allowed)


async def require_api_key(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    keys = request.app.state.settings.api_key_list
    if not keys:
        return  # open mode (dev) — a warning is logged at startup
    if not x_api_key or not key_is_valid(x_api_key, keys):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")
