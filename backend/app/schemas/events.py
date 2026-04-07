from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.common import ApiModel, EventType, LocationMode


class EventRead(ApiModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    raw_message_id: str
    event_type: EventType
    location_mode: LocationMode
    is_precise: bool
    location_id: str | None = None
    region_id: str | None = None
    location_name: str | None = None
    region_slug: str | None = None
    region_name: str | None = None
    event_time: datetime
    source_text: str
    latitude: float | None = None
    longitude: float | None = None


class EventListResponse(ApiModel):
    items: list[EventRead]
    total: int
    limit: int
    offset: int


class MapPoint(ApiModel):
    id: str
    raw_message_id: str
    event_type: EventType
    latitude: float
    longitude: float
    location_name: str | None = None
    event_time: datetime
    source_text: str


class RegionalEventRead(ApiModel):
    id: str
    event_type: EventType
    region_slug: str
    region_name: str
    event_time: datetime
    source_text: str


class MapEventsResponse(ApiModel):
    points: list[MapPoint]
    regional_events: list[RegionalEventRead]
