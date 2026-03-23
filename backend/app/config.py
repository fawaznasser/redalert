from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]


def _resolve_sqlite_url(url: str) -> str:
    if not url.startswith("sqlite:///"):
        return url

    raw_path = url.replace("sqlite:///", "", 1)
    if raw_path in {"", ":memory:"}:
        return url

    path = Path(raw_path)
    if not path.is_absolute():
        path = (BASE_DIR / path).resolve()
    return f"sqlite:///{path.as_posix()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        enable_decoding=False,
    )

    app_name: str = "Telegram Red Zone Dashboard API"
    database_url: str = "sqlite:///./data/red_alert.db"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    telegram_enabled: bool = False
    telegram_api_id: int | None = None
    telegram_api_hash: str | None = None
    telegram_session: str | None = None
    telegram_channel: str | None = None
    telegram_history_backfill_limit: int = 50
    telegram_poll_interval_seconds: int = 5
    telegram_edit_sync_limit: int = 15
    nominatim_enabled: bool = False
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    nominatim_user_agent: str = "red-alert-dashboard/1.0"
    nominatim_email: str | None = None
    nominatim_country_codes: str = "lb"
    nominatim_limit: int = 5
    default_region_slug: str = "south-lebanon"

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: Any) -> str:
        if value is None:
            return _resolve_sqlite_url("sqlite:///./data/red_alert.db")
        return _resolve_sqlite_url(str(value))

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, list):
            return value
        if value is None:
            return ["http://localhost:3000", "http://127.0.0.1:3000"]

        text = str(value).strip()
        if not text:
            return ["http://localhost:3000", "http://127.0.0.1:3000"]
        if text.startswith("["):
            return json.loads(text)
        return [item.strip() for item in text.split(",") if item.strip()]

    @property
    def telegram_is_configured(self) -> bool:
        return bool(
            self.telegram_enabled
            and self.telegram_api_id
            and self.telegram_api_hash
            and self.telegram_session
            and self.telegram_channel
        )


settings = Settings()
