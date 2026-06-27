"""12-factor configuration via pydantic-settings. Validated at startup."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AEGIS_", env_file=".env", extra="ignore")

    # SQLite for zero-infra local/dev; set to a postgres:// URL in production.
    database_url: str = "sqlite:///./aegis.db"
    # Comma-separated API keys. Empty => open (dev only; a warning is logged).
    api_keys: str = ""
    # Secret used to tokenize (HMAC) user identifiers before storage/logging.
    pii_secret: str = "dev-insecure-change-me"
    log_level: str = "INFO"
    # Comma-separated allowed CORS origins (empty => CORS disabled).
    cors_origins: str = ""
    # Per-client requests/minute on /v1 (0 => disabled).
    rate_limit_per_minute: int = 0

    # Policy thresholds (proportional response).
    score_step_up: int = 20
    score_review: int = 45
    score_block: int = 70
    impossible_travel_kmh: float = 900.0
    velocity_threshold: int = 5
    large_amount: float = 100_000.0

    @property
    def api_key_list(self) -> list[str]:
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
