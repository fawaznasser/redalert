from __future__ import annotations

from datetime import datetime

from app.schemas.common import ApiModel, AttackSide, EventType


class RawMessageRead(ApiModel):
    id: str
    telegram_message_id: str | None = None
    channel_name: str
    message_text: str
    message_date: datetime
    ingested_at: datetime
    parsed_event_type: EventType | None = None
    attack_side: AttackSide | None = None
    event_types: list[EventType]
    candidate_locations: list[str]
    matched_locations: list[str]
    unmatched_locations: list[str]


class RawMessageListResponse(ApiModel):
    items: list[RawMessageRead]
    total: int
    limit: int
