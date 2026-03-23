from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, field_serializer


class EventType(str, Enum):
    drone_movement = "drone_movement"
    fighter_jet_movement = "fighter_jet_movement"
    helicopter_movement = "helicopter_movement"


class LocationMode(str, Enum):
    exact = "exact"
    regional = "regional"


class HealthResponse(BaseModel):
    status: str
    database: str
    telegram_listener: str


def serialize_api_datetime(value: datetime) -> str:
    normalized = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return normalized.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class ApiModel(BaseModel):
    @field_serializer("event_time", "message_date", "ingested_at", "snapshot_at", check_fields=False)
    def _serialize_datetime_fields(self, value: datetime) -> str:
        return serialize_api_datetime(value)
