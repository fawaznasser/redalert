from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.raw_message import RawMessage
from app.schemas.common import EventType
from app.schemas.raw_messages import RawMessageRead
from app.services.location_matcher import match_locations
from app.services.parser import parse_message_text


def serialize_raw_message(session: Session, raw_message: RawMessage) -> RawMessageRead:
    parsed = parse_message_text(raw_message.message_text)
    candidate_locations = parsed.candidate_locations if parsed else []
    matches = match_locations(session, candidate_locations) if candidate_locations else None
    event_types = [EventType(event.event_type) for event in raw_message.events]
    parsed_event_type = parsed.event_type if parsed and parsed.event_type is not None else (event_types[0] if event_types else None)

    return RawMessageRead(
        id=raw_message.id,
        telegram_message_id=raw_message.telegram_message_id,
        channel_name=raw_message.channel_name,
        message_text=raw_message.message_text,
        message_date=raw_message.message_date,
        ingested_at=raw_message.ingested_at,
        parsed_event_type=parsed_event_type,
        event_types=event_types,
        candidate_locations=candidate_locations,
        matched_locations=[match.location.name_ar for match in matches.matches] if matches else [],
        unmatched_locations=matches.unmatched if matches else [],
    )


def list_recent_raw_messages(session: Session, *, limit: int = 10) -> tuple[int, list[RawMessageRead]]:
    total = session.scalar(select(func.count(RawMessage.id))) or 0
    stmt = (
        select(RawMessage)
        .options(selectinload(RawMessage.events))
        .order_by(RawMessage.ingested_at.desc())
        .limit(limit)
    )
    rows = session.scalars(stmt).all()
    return total, [serialize_raw_message(session, row) for row in rows]
