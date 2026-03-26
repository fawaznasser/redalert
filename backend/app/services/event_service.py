from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.models.event import Event
from app.models.location import Location
from app.models.raw_message import RawMessage
from app.models.region import Region
from app.schemas.common import EventType, LocationMode
from app.services.live_updates import live_updates
from app.services.location_matcher import LocationMatchResult, match_locations
from app.services.parser import ParsedTelegramMessage, SpatialHint, parse_message_text, parse_secondary_channel_incursion_message

logger = logging.getLogger(__name__)

EVENT_ACTIVE_WINDOWS = {
    EventType.drone_movement.value: timedelta(hours=5),
    EventType.fighter_jet_movement.value: timedelta(minutes=20),
    EventType.helicopter_movement.value: timedelta(minutes=30),
    EventType.ground_incursion.value: timedelta(hours=5),
}
CONTINUATION_LOOKBACK = timedelta(hours=6)


@dataclass(slots=True)
class IngestResult:
    raw_message: RawMessage
    events: list[Event]
    parsed_message: ParsedTelegramMessage | None
    location_matches: LocationMatchResult | None


def _serialize_raw_payload(raw_payload: dict | str | None) -> str | None:
    if raw_payload is None:
        return None
    if isinstance(raw_payload, str):
        return raw_payload
    return json.dumps(raw_payload, ensure_ascii=False)


def _ensure_aware_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _normalize_channel_name(value: str | None) -> str | None:
    if not value:
        return None
    channel = value.strip()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
        if channel.startswith(prefix):
            channel = channel[len(prefix):]
            break
    return channel.removeprefix("@").strip() or None


def _filter_event_type_for_channel(channel_name: str, event_type: EventType | None) -> EventType | None:
    if event_type is None:
        return None

    normalized_channel = _normalize_channel_name(channel_name)
    primary_channel = _normalize_channel_name(settings.telegram_channel)
    secondary_channel = _normalize_channel_name(settings.telegram_secondary_channel)

    if normalized_channel == secondary_channel:
        return event_type if event_type == EventType.ground_incursion else None

    if normalized_channel == primary_channel:
        return None if event_type == EventType.ground_incursion else event_type

    return event_type


def _parse_message_for_channel(channel_name: str, source_text: str) -> ParsedTelegramMessage | None:
    normalized_channel = _normalize_channel_name(channel_name)
    secondary_channel = _normalize_channel_name(settings.telegram_secondary_channel)

    if normalized_channel == secondary_channel:
        return parse_secondary_channel_incursion_message(source_text)

    return parse_message_text(source_text)


def _publish_raw_update(
    *,
    raw_message: RawMessage,
    event_time: datetime,
    created_events: list[Event],
) -> None:
    live_updates.publish_from_thread(
        {
            "kind": "raw_message_ingested",
            "raw_message_id": raw_message.id,
            "telegram_message_id": raw_message.telegram_message_id,
            "created_event_count": len(created_events),
            "event_types": [event.event_type for event in created_events],
            "timestamp": event_time.isoformat(),
        }
    )


def _raw_message_is_unchanged(
    raw_message: RawMessage,
    *,
    source_text: str,
    event_time: datetime,
    serialized_payload: str | None,
) -> bool:
    return (
        (raw_message.message_text or "") == source_text
        and _ensure_aware_datetime(raw_message.message_date) == event_time
        and raw_message.raw_json == serialized_payload
    )


def _get_existing_raw_message(
    session: Session,
    *,
    telegram_message_id: str | int | None,
    channel_name: str,
) -> RawMessage | None:
    if telegram_message_id is None:
        return None

    return session.scalar(
        select(RawMessage)
        .options(selectinload(RawMessage.events))
        .where(
            RawMessage.telegram_message_id == str(telegram_message_id),
            RawMessage.channel_name == channel_name,
        )
        .order_by(RawMessage.ingested_at.desc())
        .limit(1)
    )


def _find_recent_exact_event(
    session: Session,
    *,
    event_type: EventType,
    location_id: str,
    event_time: datetime,
) -> Event | None:
    return session.scalar(
        select(Event)
        .where(
            Event.event_type == event_type.value,
            Event.location_id == location_id,
            Event.location_mode == LocationMode.exact.value,
            Event.event_time >= event_time - CONTINUATION_LOOKBACK,
        )
        .order_by(Event.event_time.desc(), Event.created_at.desc())
        .limit(1)
    )


def _find_recent_regional_event(
    session: Session,
    *,
    event_type: EventType,
    region_id: str,
    event_time: datetime,
) -> Event | None:
    return session.scalar(
        select(Event)
        .where(
            Event.event_type == event_type.value,
            Event.region_id == region_id,
            Event.location_mode == LocationMode.regional.value,
            Event.event_time >= event_time - CONTINUATION_LOOKBACK,
        )
        .order_by(Event.event_time.desc(), Event.created_at.desc())
        .limit(1)
    )


def _build_inferred_coordinates(spatial_hint: SpatialHint, location_matches: LocationMatchResult) -> tuple[float, float] | None:
    if spatial_hint.mode == "between" and len(location_matches.matches) >= 2:
        first = location_matches.matches[0].location
        second = location_matches.matches[1].location
        return ((first.latitude + second.latitude) / 2, (first.longitude + second.longitude) / 2)

    if spatial_hint.mode == "above" and location_matches.matches:
        anchor = location_matches.matches[0].location
        return (anchor.latitude + 0.008, anchor.longitude)

    if spatial_hint.mode == "vicinity" and location_matches.matches:
        anchor = location_matches.matches[0].location
        return (anchor.latitude + 0.0035, anchor.longitude + 0.0035)

    return None


def _build_inferred_event(
    *,
    raw_message: RawMessage,
    parsed_message: ParsedTelegramMessage,
    event_time: datetime,
    source_text: str,
    spatial_hint: SpatialHint,
    location_matches: LocationMatchResult,
) -> Event | None:
    coordinates = _build_inferred_coordinates(spatial_hint, location_matches)
    if coordinates is None:
        return None

    return Event(
        raw_message_id=raw_message.id,
        event_type=parsed_message.event_type.value,
        location_id=None,
        region_id=None,
        location_mode=LocationMode.inferred.value,
        is_precise=False,
        location_name_raw=spatial_hint.label,
        event_time=event_time,
        source_text=source_text,
        latitude=coordinates[0],
        longitude=coordinates[1],
    )


def build_events_for_raw_message(
    session: Session,
    *,
    raw_message: RawMessage,
    parsed_message: ParsedTelegramMessage,
    location_matches: LocationMatchResult,
) -> list[Event]:
    source_text = raw_message.message_text or ""
    event_time = _ensure_aware_datetime(raw_message.message_date)
    effective_event_type = parsed_message.event_type

    if effective_event_type is None:
        return []

    collected_events: list[Event] = []
    new_events: list[Event] = []

    if location_matches.matches:
        for matched in location_matches.matches:
            location: Location = matched.location
            existing_event = (
                _find_recent_exact_event(
                    session,
                    event_type=effective_event_type,
                    location_id=location.id,
                    event_time=event_time,
                )
                if parsed_message.is_continuation
                else None
            )
            if existing_event is not None:
                existing_event.raw_message_id = raw_message.id
                existing_event.event_time = event_time
                existing_event.source_text = source_text
                existing_event.location_name_raw = matched.source_name
                existing_event.latitude = location.latitude
                existing_event.longitude = location.longitude
                collected_events.append(existing_event)
                continue

            event = Event(
                raw_message_id=raw_message.id,
                event_type=effective_event_type.value,
                location_id=location.id,
                region_id=None,
                location_mode=LocationMode.exact.value,
                is_precise=True,
                location_name_raw=matched.source_name,
                event_time=event_time,
                source_text=source_text,
                latitude=location.latitude,
                longitude=location.longitude,
            )
            new_events.append(event)
            collected_events.append(event)
    elif effective_event_type == EventType.fighter_jet_movement:
        region = session.scalar(select(Region).where(Region.slug == settings.default_region_slug))
        if region is None:
            logger.warning("Regional fighter event skipped because region '%s' is not seeded", settings.default_region_slug)
        else:
            existing_event = (
                _find_recent_regional_event(
                    session,
                    event_type=effective_event_type,
                    region_id=region.id,
                    event_time=event_time,
                )
                if parsed_message.is_continuation
                else None
            )
            if existing_event is not None:
                existing_event.raw_message_id = raw_message.id
                existing_event.event_time = event_time
                existing_event.source_text = source_text
                collected_events.append(existing_event)
            else:
                event = Event(
                    raw_message_id=raw_message.id,
                    event_type=effective_event_type.value,
                    location_id=None,
                    region_id=region.id,
                    location_mode=LocationMode.regional.value,
                    is_precise=False,
                    location_name_raw=None,
                    event_time=event_time,
                    source_text=source_text,
                    latitude=None,
                    longitude=None,
                )
                new_events.append(event)
                collected_events.append(event)
    elif parsed_message.spatial_hint is not None:
        anchor_matches = match_locations(session, parsed_message.spatial_hint.anchor_candidates)
        inferred_event = _build_inferred_event(
            raw_message=raw_message,
            parsed_message=parsed_message,
            event_time=event_time,
            source_text=source_text,
            spatial_hint=parsed_message.spatial_hint,
            location_matches=anchor_matches,
        )
        if inferred_event is not None:
            new_events.append(inferred_event)
            collected_events.append(inferred_event)

    if new_events:
        session.add_all(new_events)

    return collected_events


def ingest_message(
    session: Session,
    *,
    telegram_message_id: str | int | None,
    channel_name: str,
    message_text: str | None,
    message_date: datetime | None,
    raw_payload: dict | str | None = None,
) -> IngestResult:
    source_text = message_text or ""
    event_time = _ensure_aware_datetime(message_date)
    serialized_payload = _serialize_raw_payload(raw_payload)
    raw_message = _get_existing_raw_message(
        session,
        telegram_message_id=telegram_message_id,
        channel_name=channel_name,
    )
    if raw_message is None:
        raw_message = RawMessage(
            telegram_message_id=str(telegram_message_id) if telegram_message_id is not None else None,
            channel_name=channel_name,
            message_text=source_text,
            message_date=event_time,
            raw_json=serialized_payload,
        )
        session.add(raw_message)
        session.flush()
    else:
        if _raw_message_is_unchanged(
            raw_message,
            source_text=source_text,
            event_time=event_time,
            serialized_payload=serialized_payload,
        ):
            parsed_message = _parse_message_for_channel(channel_name, source_text)
            location_matches = match_locations(session, parsed_message.candidate_locations) if parsed_message else None
            return IngestResult(
                raw_message=raw_message,
                events=list(raw_message.events),
                parsed_message=parsed_message,
                location_matches=location_matches,
            )
        raw_message.message_text = source_text
        raw_message.message_date = event_time
        raw_message.raw_json = serialized_payload
        raw_message.ingested_at = datetime.now(timezone.utc)
        for existing_event in list(raw_message.events):
            session.delete(existing_event)
        session.flush()

    parsed_message = _parse_message_for_channel(channel_name, source_text)
    if parsed_message is None:
        session.commit()
        session.refresh(raw_message)
        _publish_raw_update(raw_message=raw_message, event_time=event_time, created_events=[])
        return IngestResult(raw_message=raw_message, events=[], parsed_message=None, location_matches=None)

    filtered_event_type = _filter_event_type_for_channel(channel_name, parsed_message.event_type)
    if filtered_event_type != parsed_message.event_type:
        parsed_message = ParsedTelegramMessage(
            event_type=filtered_event_type,
            event_tag=parsed_message.event_tag,
            hashtags=parsed_message.hashtags,
            candidate_locations=parsed_message.candidate_locations,
            is_continuation=parsed_message.is_continuation,
        )

    location_matches = match_locations(session, parsed_message.candidate_locations)
    if parsed_message.event_type is None:
        session.commit()
        session.refresh(raw_message)
        _publish_raw_update(raw_message=raw_message, event_time=event_time, created_events=[])
        return IngestResult(raw_message=raw_message, events=[], parsed_message=parsed_message, location_matches=location_matches)

    created_events = build_events_for_raw_message(
        session,
        raw_message=raw_message,
        parsed_message=parsed_message,
        location_matches=location_matches,
    )

    session.commit()

    session.refresh(raw_message)
    for event in created_events:
        session.refresh(event)

    _publish_raw_update(raw_message=raw_message, event_time=event_time, created_events=created_events)

    return IngestResult(
        raw_message=raw_message,
        events=created_events,
        parsed_message=parsed_message,
        location_matches=location_matches,
    )


def _apply_event_filters(
    stmt,
    *,
    event_type: EventType | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    location_mode: LocationMode | None = None,
    active_only: bool = True,
):
    if active_only:
        now = datetime.now(timezone.utc)
        stmt = stmt.where(_active_event_clause(now))
    if event_type is not None:
        stmt = stmt.where(Event.event_type == event_type.value)
    if from_date is not None:
        stmt = stmt.where(Event.event_time >= from_date)
    if to_date is not None:
        stmt = stmt.where(Event.event_time <= to_date)
    if location_mode is not None:
        stmt = stmt.where(Event.location_mode == location_mode.value)
    return stmt


def _active_event_clause(now: datetime):
    return or_(
        and_(
            Event.event_type == EventType.drone_movement.value,
            Event.event_time >= now - EVENT_ACTIVE_WINDOWS[EventType.drone_movement.value],
        ),
        and_(
            Event.event_type == EventType.fighter_jet_movement.value,
            Event.event_time >= now - EVENT_ACTIVE_WINDOWS[EventType.fighter_jet_movement.value],
        ),
        and_(
            Event.event_type == EventType.helicopter_movement.value,
            Event.event_time >= now - EVENT_ACTIVE_WINDOWS[EventType.helicopter_movement.value],
        ),
        and_(
            Event.event_type == EventType.ground_incursion.value,
            Event.event_time >= now - EVENT_ACTIVE_WINDOWS[EventType.ground_incursion.value],
        ),
    )


def list_events(
    session: Session,
    *,
    event_type: EventType | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    location_mode: LocationMode | None = None,
    limit: int = 50,
    offset: int = 0,
    active_only: bool = True,
) -> tuple[int, list[Event]]:
    stmt = _apply_event_filters(
        select(Event)
        .options(selectinload(Event.location), selectinload(Event.region))
        .order_by(Event.event_time.desc(), Event.created_at.desc()),
        event_type=event_type,
        from_date=from_date,
        to_date=to_date,
        location_mode=location_mode,
        active_only=active_only,
    )

    items = _dedupe_feed_events(session.scalars(stmt).all())
    total = len(items)
    return total, items[offset : offset + limit]


def get_map_events(
    session: Session,
    *,
    event_type: EventType | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    active_only: bool = True,
) -> tuple[list[Event], list[Event]]:
    points_stmt = _apply_event_filters(
        select(Event)
        .options(selectinload(Event.location))
        .where(Event.location_mode.in_([LocationMode.exact.value, LocationMode.inferred.value]))
        .order_by(Event.event_time.desc()),
        event_type=event_type,
        from_date=from_date,
        to_date=to_date,
        active_only=active_only,
    )
    regional_stmt = _apply_event_filters(
        select(Event)
        .options(selectinload(Event.region))
        .where(Event.location_mode == LocationMode.regional.value)
        .order_by(Event.event_time.desc()),
        event_type=event_type,
        from_date=from_date,
        to_date=to_date,
        active_only=active_only,
    )
    return _dedupe_map_events(session.scalars(points_stmt).all()), _dedupe_map_events(session.scalars(regional_stmt).all())


def _dedupe_map_events(events: list[Event]) -> list[Event]:
    unique_events: list[Event] = []
    seen_keys: set[tuple[str, str | None, str | None, float | None, float | None]] = set()

    for event in events:
        dedupe_key = (
            event.event_type,
            event.location_id,
            event.region_id,
            event.latitude,
            event.longitude,
        )
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        unique_events.append(event)

    return unique_events


def _dedupe_feed_events(events: list[Event]) -> list[Event]:
    unique_events: list[Event] = []
    seen_keys: set[tuple[str, str | None, str | None, str, str | None, str]] = set()

    for event in events:
        dedupe_key = (
            event.event_type,
            event.location_id,
            event.region_id,
            _ensure_aware_datetime(event.event_time).isoformat(),
            event.location_name_raw,
            (event.source_text or "").strip(),
        )
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        unique_events.append(event)

    return unique_events


def get_stats(session: Session) -> dict[str, int]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    active_clause = _active_event_clause(datetime.now(timezone.utc))

    def count(*filters) -> int:
        return session.scalar(select(func.count(Event.id)).where(*filters)) or 0

    return {
        "total_events": count(active_clause),
        "drone_count": count(active_clause, Event.event_type == EventType.drone_movement.value),
        "fighter_count": count(active_clause, Event.event_type == EventType.fighter_jet_movement.value),
        "helicopter_count": count(active_clause, Event.event_type == EventType.helicopter_movement.value),
        "exact_count": count(active_clause, Event.location_mode == LocationMode.exact.value),
        "regional_count": count(active_clause, Event.location_mode == LocationMode.regional.value),
        "last_24h_total": count(Event.event_time >= cutoff),
        "last_24h_drone_count": count(
            Event.event_time >= cutoff,
            Event.event_type == EventType.drone_movement.value,
        ),
        "last_24h_fighter_count": count(
            Event.event_time >= cutoff,
            Event.event_type == EventType.fighter_jet_movement.value,
        ),
        "last_24h_helicopter_count": count(
            Event.event_time >= cutoff,
            Event.event_type == EventType.helicopter_movement.value,
        ),
    }


def get_stats_for_filters(
    session: Session,
    *,
    event_type: EventType | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    location_mode: LocationMode | None = None,
    active_only: bool = True,
) -> dict[str, int]:
    stmt = _apply_event_filters(
        select(Event),
        event_type=event_type,
        from_date=from_date,
        to_date=to_date,
        location_mode=location_mode,
        active_only=active_only,
    )
    subquery = stmt.subquery()

    def count(*filters) -> int:
        return session.scalar(select(func.count()).select_from(subquery).where(*filters)) or 0

    return {
        "total_events": count(),
        "drone_count": count(subquery.c.event_type == EventType.drone_movement.value),
        "fighter_count": count(subquery.c.event_type == EventType.fighter_jet_movement.value),
        "helicopter_count": count(subquery.c.event_type == EventType.helicopter_movement.value),
        "exact_count": count(subquery.c.location_mode == LocationMode.exact.value),
        "regional_count": count(subquery.c.location_mode == LocationMode.regional.value),
        "last_24h_total": count(),
        "last_24h_drone_count": count(subquery.c.event_type == EventType.drone_movement.value),
        "last_24h_fighter_count": count(subquery.c.event_type == EventType.fighter_jet_movement.value),
        "last_24h_helicopter_count": count(subquery.c.event_type == EventType.helicopter_movement.value),
    }
