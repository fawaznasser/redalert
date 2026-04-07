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
from app.services.parser import (
    ParsedTelegramMessage,
    SpatialHint,
    extract_hashtags,
    extract_spatial_hint,
    extract_text_location_candidates,
    is_location_candidate,
    normalize_text,
    parse_message_text,
    parse_rnn_channel_message,
    parse_secondary_channel_incursion_message,
)

logger = logging.getLogger(__name__)

REDLINK_PRIMARY_CHANNEL = "redlinkleb"

EVENT_ACTIVE_WINDOWS = {
    EventType.drone_movement.value: timedelta(hours=5),
    EventType.fighter_jet_movement.value: timedelta(minutes=20),
    EventType.helicopter_movement.value: timedelta(minutes=30),
    EventType.ground_incursion.value: timedelta(hours=5),
}
CONTINUATION_LOOKBACK = timedelta(hours=6)
LEBANON_MAP_BOUNDS = ((33.05, 35.08), (34.72, 36.62))
ISRAEL_LOCATION_KEYWORDS = (
    "كريات شمونة",
    "المطلة",
    "مرجليوت",
    "مرغليوت",
    "نهاريا",
    "صفد",
    "طبريا",
    "بحيرة طبريا",
    "عميعاد",
    "افيفيم",
    "أفيفيم",
    "ادميت",
    "أدميت",
    "روش بينا",
    "حيفا",
    "تل ابيب",
    "تل أبيب",
    "الجليل",
    "ميرون",
    "شلومي",
)
COMBAT_MESSAGE_PATTERNS = (
    "%غارة%",
    "%قصف%",
    "%استهداف%",
    "%ضربة%",
    "%هجوم بطائرات مسيرة%",
    "%هجوم بطائرات مسيّرة%",
    "%هجوم بصاروخ%",
    "%صاروخ مضاد للدروع%",
    "%عملية مقاومة%",
    "%عمليات المقاومة%",
    "%اشتباكات%",
    "%اشتباك%",
    "%توغل%",
    "%تسلل%",
    "%إطلاق صاروخ%",
    "%اطلاق صاروخ%",
    "%إسقاط طائرة مسيّرة%",
    "%إسقاط طائرة مسيرة%",
    "%يسقط مسيرة%",
    "%يسقط طائرة%",
    "%تدمير%",
)


@dataclass(slots=True)
class IngestResult:
    raw_message: RawMessage
    events: list[Event]
    parsed_message: ParsedTelegramMessage | None
    location_matches: LocationMatchResult | None


def _get_raw_message_text(event: Event) -> str:
    if getattr(event, "source_text", None):
        return str(event.source_text)
    raw_message = getattr(event, "raw_message", None)
    if raw_message is not None and getattr(raw_message, "message_text", None):
        return str(raw_message.message_text)
    return ""


def _event_coordinates(event: Event) -> tuple[float | None, float | None]:
    latitude = getattr(event, "latitude", None)
    longitude = getattr(event, "longitude", None)
    if latitude is not None and longitude is not None:
        return latitude, longitude

    location = getattr(event, "location", None)
    if location is not None:
        location_latitude = getattr(location, "latitude", None)
        location_longitude = getattr(location, "longitude", None)
        if location_latitude is not None and location_longitude is not None:
            return location_latitude, location_longitude

    return None, None


def _event_is_outside_lebanon(event: Event) -> bool:
    location = getattr(event, "location", None)
    if location is not None:
        governorate = str(getattr(location, "governorate", "") or "").lower()
        district = str(getattr(location, "district", "") or "").lower()
        name_en = str(getattr(location, "name_en", "") or "").lower()
        if "israel" in governorate or "israel" in district or "israel" in name_en:
            return True

    text = normalize_text(_get_raw_message_text(event))
    if _has_any_keyword(text, ISRAEL_LOCATION_KEYWORDS):
        return True

    latitude, longitude = _event_coordinates(event)
    if latitude is None or longitude is None:
        return False

    (min_lat, min_lng), (max_lat, max_lng) = LEBANON_MAP_BOUNDS
    return latitude < min_lat or latitude > max_lat or longitude < min_lng or longitude > max_lng


def _has_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _is_actual_incursion_text(text: str) -> bool:
    if _has_any_keyword(
        text,
        (
            "توغل",
            "توغل بري",
            "محاولات توغل",
            "عمليات توغل",
            "عملية توغل",
            "متوغل",
            "متوغلة",
        ),
    ):
        return True

    return "تسلل" in text and "مسير" not in text and "طائرة" not in text and "مسي" not in text


def _infer_attack_side_from_text(event: Event) -> str | None:
    text = normalize_text(_get_raw_message_text(event))
    if not text:
        return None

    enemy_summary_keywords = (
        "ملخص الاعتداءات الاسرائيلية على الاراضي اللبنانية",
        "ملخص الاعتداءات الإسرائيلية على الأراضي اللبنانية",
        "الاعتداءات الاسرائيلية على الاراضي اللبنانية",
        "الاعتداءات الإسرائيلية على الأراضي اللبنانية",
        "الغارات التي نفذها الطيران الحربي المعادي",
        "الطيران الحربي المعادي",
    )

    israel_target_keywords = (
        "كريات شمونة",
        "كريات_شمونة",
        "المطلة",
        "مرجليوت",
        "مرغليوت",
        "شلومي",
        "صفد",
        "نهاريا",
        "طبريا",
        "بحيرة طبريا",
        "حيفا",
        "تل ابيب",
        "تل أبيب",
        "ميرون",
        "عميعاد",
        "قاعدة عميعاد",
        "افيفيم",
        "أفيفيم",
        "ادميت",
        "أدميت",
        "روش بينا",
        "الجليل",
        "مسكاف عام",
        "المنارة",
        "منارة",
    )

    has_resistance_keywords = _has_any_keyword(
        text,
        (
            "عملية مقاومة",
            "عمليات المقاومة",
            "جنود الاحتلال",
            "قوات الاحتلال",
            "موقع الاحتلال",
            "مواقع الاحتلال",
            "تجمع لجنود الاحتلال",
            "مستوطنة",
            "مستعمرات",
            "ميركافا",
            "دبابة",
            "دبابه",
            "صاروخ دفاع جوي",
            "اطلاق صاروخ",
            "إطلاق صاروخ",
            "صاروخ مضاد للدروع",
            "تدمير دبابة",
            "اسقاط طائرة مسيرة",
            "إسقاط طائرة مسيرة",
            "اسقاط طائرة مسيرة",
            "إسقاط طائرة مسيرة",
            "يسقط مسيرة",
            "يسقط طائرة",
        ),
    )
    has_strong_hezbollah_markers = _has_any_keyword(
        text,
        (
            "حزب الله",
            "ميركافا",
            "استهداف دبابة",
            "إصابة مباشرة لدبابة",
            "اصابة مباشرة لدبابة",
            "إصابة مباشرة لآلية عسكرية",
            "اصابة مباشرة لآلية عسكرية",
            "استهداف قوة إسرائيلية",
            "استهداف جنود العدو",
            "استهداف جنود الاحتلال",
            "استهداف تجمع لجنود الاحتلال",
            "استهداف آلية عسكرية",
            "قذائف التاندوم",
            "كورنيت",
            "قوة الرضوان",
            "قوات الرضوان",
        ),
    )
    has_attack_keywords = _has_any_keyword(
        text,
        (
            "غارة",
            "قصف",
            "استهداف",
            "ضربة",
            "هجوم بطائرات مسيرة",
            "هجوم بطائرات مسيرة",
            "هجوم بصاروخ",
            "صاروخ مضاد للدروع",
            "تدمير",
            "نسف",
            "تفجير",
            "اشتباك",
            "اشتباكات",
        ),
    )
    has_drone_attack = _has_any_keyword(
        text,
        (
            "هجوم بطائرات مسيرة",
            "هجوم بطائرات مسيرة",
            "بمسيّرة",
            "بمسيرة",
            "انقضاضي",
        ),
    )
    has_enemy_keywords = _has_any_keyword(
        text,
        (
            "غارة",
            "قصف",
            "نسف",
            "تفجير منازل",
            "ضربة",
        ),
    )
    outside_lebanon = _event_is_outside_lebanon(event)
    mentions_enemy_summary = _has_any_keyword(text, enemy_summary_keywords)
    mentions_israel_targets = _has_any_keyword(text, israel_target_keywords)

    if mentions_enemy_summary:
        return "enemy_attack"

    if not outside_lebanon and _has_any_keyword(text, ("ضربات حزب الله على مواقع عسكرية",)):
        return None

    if has_strong_hezbollah_markers and not _is_actual_incursion_text(text):
        return "resistance_attack"

    if has_resistance_keywords and not _is_actual_incursion_text(text):
        if not outside_lebanon and mentions_israel_targets and not has_enemy_keywords:
            return None
        return "resistance_attack"

    if _is_actual_incursion_text(text):
        return None

    if outside_lebanon and has_attack_keywords:
        return "resistance_attack"

    if has_drone_attack:
        return "resistance_attack" if outside_lebanon or has_resistance_keywords else "enemy_attack"

    if has_enemy_keywords:
        return "enemy_attack"

    if _has_any_keyword(text, ("اشتباك", "اشتباكات")) and (outside_lebanon or has_resistance_keywords):
        return "resistance_attack"

    return None


def _should_suppress_local_resistance_side(event: Event) -> bool:
    text = normalize_text(_get_raw_message_text(event))
    if not text:
        return False
    if _event_is_outside_lebanon(event):
        return False
    if _has_any_keyword(
        text,
        (
            "ضربات حزب الله على مواقع عسكرية",
            "استهداف مقر قيادة المنطقة الشمالية",
            "انفجارات في كريات شمونة",
            "عبور مسيرات باتجاه كريات شمونة",
            "سقوط مسيرة في منطقة صفد",
        ),
    ):
        return True
    if not _has_any_keyword(
        text,
        (
            "عملية مقاومة",
            "عمليات المقاومة",
            "استهداف",
            "هجوم بصاروخ",
            "صاروخ مضاد للدروع",
            "هجوم بطائرات مسيرة",
            "هجوم بطائرات مسيّرة",
        ),
    ):
        return False
    return _has_any_keyword(
        text,
        (
            "كريات شمونة",
            "كريات_شمونة",
            "المطلة",
            "مرجليوت",
            "مرغليوت",
            "شلومي",
            "صفد",
            "نهاريا",
            "طبريا",
            "بحيرة طبريا",
            "حيفا",
            "تل ابيب",
            "تل أبيب",
            "ميرون",
            "عميعاد",
            "قاعدة عميعاد",
            "افيفيم",
            "أفيفيم",
            "ادميت",
            "أدميت",
            "روش بينا",
            "الجليل",
            "مسكاف عام",
            "المنارة",
            "منارة",
        ),
    )


def get_event_attack_side(event: Event) -> str | None:
    channel_name = event.raw_message.channel_name if event.raw_message is not None else None
    if _is_redlink_channel(channel_name):
        return None

    raw_json = event.raw_message.raw_json if event.raw_message is not None else None
    if not raw_json:
        return _infer_attack_side_from_text(event)

    try:
        payload = json.loads(raw_json)
    except (TypeError, json.JSONDecodeError):
        return _infer_attack_side_from_text(event)

    if not isinstance(payload, dict):
        return _infer_attack_side_from_text(event)

    ocr_payload = payload.get("_ocr")
    if not isinstance(ocr_payload, dict):
        return _infer_attack_side_from_text(event)

    attack_side = ocr_payload.get("attack_side")
    if attack_side in {"enemy_attack", "resistance_attack"}:
        return attack_side

    return _infer_attack_side_from_text(event)


def _extract_ocr_payload(raw_payload: dict | str | None) -> dict | None:
    if raw_payload is None:
        return None
    if isinstance(raw_payload, str):
        try:
            raw_payload = json.loads(raw_payload)
        except (TypeError, json.JSONDecodeError):
            return None
    if not isinstance(raw_payload, dict):
        return None
    ocr_payload = raw_payload.get("_ocr")
    return ocr_payload if isinstance(ocr_payload, dict) else None


def _build_color_hint_parsed_message(source_text: str, label_color: str) -> ParsedTelegramMessage | None:
    if label_color != "green":
        return None

    hashtags = extract_hashtags(source_text)
    candidate_locations: list[str] = []
    for tag in hashtags:
        if is_location_candidate(tag) and tag not in candidate_locations:
            candidate_locations.append(tag)
    for candidate in extract_text_location_candidates(source_text):
        if candidate not in candidate_locations:
            candidate_locations.append(candidate)

    return ParsedTelegramMessage(
        event_type=EventType.ground_incursion,
        event_tag="green_label",
        hashtags=hashtags,
        candidate_locations=candidate_locations,
        is_continuation=False,
        spatial_hint=extract_spatial_hint(source_text),
    )


def _apply_media_hints(
    channel_name: str,
    source_text: str,
    parsed_message: ParsedTelegramMessage | None,
    raw_payload: dict | str | None,
) -> ParsedTelegramMessage | None:
    ocr_payload = _extract_ocr_payload(raw_payload)
    label_color = ""
    if ocr_payload is not None:
        label_color = str(ocr_payload.get("label_color") or "").strip().lower()
    has_green_incursion_hint = label_color == "green"

    if parsed_message is not None and parsed_message.event_type == EventType.ground_incursion and not has_green_incursion_hint:
        filtered_event_type = _filter_event_type_for_channel(channel_name, EventType.fighter_jet_movement)
        return ParsedTelegramMessage(
            event_type=filtered_event_type,
            event_tag=parsed_message.event_tag,
            hashtags=parsed_message.hashtags,
            candidate_locations=parsed_message.candidate_locations,
            is_continuation=parsed_message.is_continuation,
            spatial_hint=parsed_message.spatial_hint,
        )

    if not label_color:
        return parsed_message

    should_force_green_incursion = _build_color_hint_parsed_message(source_text, label_color)

    if parsed_message is None:
        hinted = should_force_green_incursion
        if hinted is not None:
            filtered_event_type = _filter_event_type_for_channel(channel_name, hinted.event_type)
            if filtered_event_type != hinted.event_type:
                return ParsedTelegramMessage(
                    event_type=filtered_event_type,
                    event_tag=hinted.event_tag,
                    hashtags=hinted.hashtags,
                    candidate_locations=hinted.candidate_locations,
                    is_continuation=hinted.is_continuation,
                    spatial_hint=hinted.spatial_hint,
                )
            return hinted
        return parsed_message

    if should_force_green_incursion is not None:
        filtered_event_type = _filter_event_type_for_channel(channel_name, should_force_green_incursion.event_type)
        return ParsedTelegramMessage(
            event_type=filtered_event_type,
            event_tag=should_force_green_incursion.event_tag,
            hashtags=parsed_message.hashtags or should_force_green_incursion.hashtags,
            candidate_locations=parsed_message.candidate_locations or should_force_green_incursion.candidate_locations,
            is_continuation=parsed_message.is_continuation,
            spatial_hint=parsed_message.spatial_hint or should_force_green_incursion.spatial_hint,
        )

    if parsed_message.event_type is None:
        hinted = should_force_green_incursion
        if hinted is not None:
            filtered_event_type = _filter_event_type_for_channel(channel_name, hinted.event_type)
            return ParsedTelegramMessage(
                event_type=filtered_event_type,
                event_tag=hinted.event_tag,
                hashtags=parsed_message.hashtags,
                candidate_locations=parsed_message.candidate_locations or hinted.candidate_locations,
                is_continuation=parsed_message.is_continuation,
                spatial_hint=parsed_message.spatial_hint or hinted.spatial_hint,
            )

    return parsed_message


def _serialize_live_event(event: Event) -> dict[str, object]:
    return {
        "id": event.id,
        "event_type": event.event_type,
        "location_mode": event.location_mode,
        "location_name": event.location.name_ar if event.location is not None else event.location_name_raw,
        "region_slug": event.region.slug if event.region is not None else None,
        "region_name": event.region.name if event.region is not None else None,
        "event_time": _ensure_aware_datetime(event.event_time).isoformat(),
        "source_text": event.source_text,
        "attack_side": get_event_attack_side(event),
        "latitude": event.latitude,
        "longitude": event.longitude,
    }


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
    normalized = channel.removeprefix("@").strip()
    return normalized.lower() or None


def _is_redlink_channel(value: str | None) -> bool:
    return _normalize_channel_name(value) == REDLINK_PRIMARY_CHANNEL


def _channel_filters_include_redlink(channel_names: list[str] | None) -> bool:
    return any(_is_redlink_channel(name) for name in (channel_names or []))


def _filter_event_type_for_channel(channel_name: str, event_type: EventType | None) -> EventType | None:
    if event_type is None:
        return None

    normalized_channel = _normalize_channel_name(channel_name)
    primary_channel = _normalize_channel_name(settings.telegram_channel)

    if normalized_channel == primary_channel and _is_redlink_channel(normalized_channel):
        return None if event_type == EventType.ground_incursion else event_type

    return event_type


def _parse_message_for_channel(channel_name: str, source_text: str) -> ParsedTelegramMessage | None:
    normalized_channel = _normalize_channel_name(channel_name)
    secondary_channel = _normalize_channel_name(settings.telegram_secondary_channel)
    if normalized_channel == "rnn_alerts_ar_lebanon":
        return parse_rnn_channel_message(source_text)

    if normalized_channel == secondary_channel:
        return parse_message_text(source_text) or parse_secondary_channel_incursion_message(source_text)

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
            "actions": [_serialize_live_event(event) for event in created_events],
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
                location=location,
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
                    region=region,
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
            parsed_message = _apply_media_hints(channel_name, source_text, _parse_message_for_channel(channel_name, source_text), serialized_payload)
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

    parsed_message = _apply_media_hints(channel_name, source_text, _parse_message_for_channel(channel_name, source_text), serialized_payload)
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


def _apply_channel_filters(stmt, *, channel_names: list[str] | None = None):
    normalized = [str(name).strip() for name in (channel_names or []) if str(name).strip()]
    if not normalized:
        return stmt
    stmt = stmt.join(Event.raw_message).where(RawMessage.channel_name.in_(normalized))

    if _channel_filters_include_redlink(normalized):
        repost_pattern = "%المناطق المتأثرة%"
        stmt = stmt.where(~func.lower(RawMessage.message_text).like(func.lower(repost_pattern)))

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


def _apply_combat_only_filters(stmt, *, channel_names: list[str] | None = None):
    normalized = [str(name).strip() for name in (channel_names or []) if str(name).strip()]
    if not normalized:
        stmt = stmt.join(Event.raw_message)

    raw_json_lower = func.lower(func.coalesce(RawMessage.raw_json, ""))
    message_text_lower = func.lower(func.coalesce(RawMessage.message_text, ""))
    attack_side_clause = or_(
        raw_json_lower.like('%"attack_side":"enemy_attack"%'),
        raw_json_lower.like('%"attack_side": "enemy_attack"%'),
        raw_json_lower.like('%"attack_side":"resistance_attack"%'),
        raw_json_lower.like('%"attack_side": "resistance_attack"%'),
    )
    message_text_clause = or_(*[message_text_lower.like(func.lower(pattern)) for pattern in COMBAT_MESSAGE_PATTERNS])

    return stmt.where(
        or_(
            Event.event_type == EventType.ground_incursion.value,
            attack_side_clause,
            message_text_clause,
        )
    )


def list_events(
    session: Session,
    *,
    event_type: EventType | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    location_mode: LocationMode | None = None,
    channel_names: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
    active_only: bool = True,
    combat_only: bool = False,
) -> tuple[int, list[Event]]:
    stmt = _apply_event_filters(
        select(Event)
        .options(selectinload(Event.location), selectinload(Event.region), selectinload(Event.raw_message))
        .order_by(Event.event_time.desc(), Event.created_at.desc()),
        event_type=event_type,
        from_date=from_date,
        to_date=to_date,
        location_mode=location_mode,
        active_only=active_only,
    )
    stmt = _apply_channel_filters(stmt, channel_names=channel_names)
    if combat_only:
        stmt = _apply_combat_only_filters(stmt, channel_names=channel_names)

    items = _dedupe_feed_events(session.scalars(stmt).all())
    total = len(items)
    return total, items[offset : offset + limit]


def get_map_events(
    session: Session,
    *,
    event_type: EventType | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    channel_names: list[str] | None = None,
    active_only: bool = True,
    combat_only: bool = False,
    map_limit: int | None = None,
) -> tuple[list[Event], list[Event]]:
    points_stmt = _apply_event_filters(
        select(Event)
        .options(selectinload(Event.location), selectinload(Event.raw_message))
        .where(Event.location_mode.in_([LocationMode.exact.value, LocationMode.inferred.value]))
        .order_by(Event.event_time.desc()),
        event_type=event_type,
        from_date=from_date,
        to_date=to_date,
        active_only=active_only,
    )
    points_stmt = _apply_channel_filters(points_stmt, channel_names=channel_names)
    if combat_only:
        points_stmt = _apply_combat_only_filters(points_stmt, channel_names=channel_names)
    if map_limit is not None:
        points_stmt = points_stmt.limit(max(map_limit * 4, map_limit))
    regional_stmt = _apply_event_filters(
        select(Event)
        .options(selectinload(Event.region), selectinload(Event.raw_message))
        .where(Event.location_mode == LocationMode.regional.value)
        .order_by(Event.event_time.desc()),
        event_type=event_type,
        from_date=from_date,
        to_date=to_date,
        active_only=active_only,
    )
    regional_stmt = _apply_channel_filters(regional_stmt, channel_names=channel_names)
    if combat_only:
        regional_stmt = _apply_combat_only_filters(regional_stmt, channel_names=channel_names)
    if map_limit is not None:
        regional_stmt = regional_stmt.limit(max(24, map_limit))
    point_events = _dedupe_map_events(session.scalars(points_stmt).all())
    regional_events = _dedupe_map_events(session.scalars(regional_stmt).all())
    if map_limit is not None:
        point_events = point_events[:map_limit]
        regional_events = regional_events[: max(6, map_limit // 4)]
    return point_events, regional_events


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


def get_stats(session: Session, *, channel_names: list[str] | None = None) -> dict[str, int]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    active_clause = _active_event_clause(datetime.now(timezone.utc))

    def count(*filters) -> int:
        stmt = select(func.count(Event.id)).select_from(Event).where(*filters)
        stmt = _apply_channel_filters(stmt, channel_names=channel_names)
        return session.scalar(stmt) or 0

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
    channel_names: list[str] | None = None,
    active_only: bool = True,
    combat_only: bool = False,
) -> dict[str, int]:
    stmt = _apply_event_filters(
        select(Event),
        event_type=event_type,
        from_date=from_date,
        to_date=to_date,
        location_mode=location_mode,
        active_only=active_only,
    )
    stmt = _apply_channel_filters(stmt, channel_names=channel_names)
    if combat_only:
        stmt = _apply_combat_only_filters(stmt, channel_names=channel_names)
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
