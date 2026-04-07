from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.region import Region
from app.schemas.common import AttackSide, EventType, LocationMode
from app.schemas.dashboard import DashboardResponse, PipelineSummary
from app.schemas.events import EventListResponse, EventRead, MapEventsResponse, MapPoint, RegionalEventRead
from app.schemas.raw_messages import RawMessageListResponse
from app.schemas.regions import RegionRead
from app.schemas.stats import StatsResponse
from app.services.event_service import get_event_attack_side, get_map_events, get_stats, get_stats_for_filters, list_events
from app.services.raw_message_service import list_recent_raw_messages

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    type: EventType | None = Query(default=None),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    channel: list[str] = Query(default=[]),
    location_mode: LocationMode | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=2000),
    map_limit: int = Query(default=250, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    raw_limit: int = Query(default=10, ge=1, le=100),
    active_only: bool = Query(default=True),
    combat_only: bool = Query(default=False),
    include_raw_messages: bool = Query(default=True),
    include_regions: bool = Query(default=True),
    include_pipeline: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> DashboardResponse:
    total, events = list_events(
        db,
        event_type=type,
        from_date=from_,
        to_date=to,
        location_mode=location_mode,
        channel_names=channel,
        limit=limit,
        offset=offset,
        active_only=active_only,
        combat_only=combat_only,
    )
    point_events, regional_events = get_map_events(
        db,
        event_type=type,
        from_date=from_,
        to_date=to,
        channel_names=channel,
        active_only=active_only,
        combat_only=combat_only,
        map_limit=map_limit,
    )
    raw_total = 0
    raw_messages = []
    if include_raw_messages or include_pipeline:
        raw_total, raw_messages = list_recent_raw_messages(db, limit=raw_limit)

    regions = db.scalars(select(Region).order_by(Region.name.asc())).all() if include_regions else []

    event_items = [
        EventRead(
            id=event.id,
            raw_message_id=event.raw_message_id,
            event_type=EventType(event.event_type),
            location_mode=LocationMode(event.location_mode),
            is_precise=event.is_precise,
            location_id=event.location_id,
            region_id=event.region_id,
            location_name=event.location.name_ar if event.location else event.location_name_raw,
            region_slug=event.region.slug if event.region else None,
            region_name=event.region.name if event.region else None,
            event_time=event.event_time,
            source_text=event.source_text,
            attack_side=AttackSide(get_event_attack_side(event)) if get_event_attack_side(event) else None,
            latitude=event.latitude,
            longitude=event.longitude,
        )
        for event in events
    ]

    map_points = [
        MapPoint(
            id=event.id,
            raw_message_id=event.raw_message_id,
            event_type=EventType(event.event_type),
            latitude=event.latitude,
            longitude=event.longitude,
            location_name=event.location.name_ar if event.location else event.location_name_raw,
            event_time=event.event_time,
            source_text=event.source_text,
            attack_side=AttackSide(get_event_attack_side(event)) if get_event_attack_side(event) else None,
        )
        for event in point_events
        if event.latitude is not None and event.longitude is not None
    ]

    map_regionals = [
        RegionalEventRead(
            id=event.id,
            event_type=EventType(event.event_type),
            region_slug=event.region.slug,
            region_name=event.region.name,
            event_time=event.event_time,
            source_text=event.source_text,
            attack_side=AttackSide(get_event_attack_side(event)) if get_event_attack_side(event) else None,
        )
        for event in regional_events
        if event.region is not None
    ]

    region_reads = (
        [
            RegionRead(id=region.id, slug=region.slug, name=region.name, geojson=json.loads(region.geojson))
            for region in regions
        ]
        if include_regions
        else []
    )

    recent_structured = sum(1 for item in raw_messages if item.event_types) if include_pipeline else 0
    recent_mapped = sum(1 for item in raw_messages if item.matched_locations) if include_pipeline else 0
    recent_unmatched = sum(1 for item in raw_messages if item.unmatched_locations) if include_pipeline else 0

    return DashboardResponse(
        snapshot_at=datetime.now(timezone.utc),
        stats=StatsResponse(
            **(
                get_stats(db)
                if active_only and from_ is None and to is None and location_mode is None and type is None and not channel
                else get_stats_for_filters(
                    db,
                    event_type=type,
                    from_date=from_,
                    to_date=to,
                    location_mode=location_mode,
                    channel_names=channel,
                    active_only=active_only,
                    combat_only=combat_only,
                )
            )
        ),
        events=EventListResponse(items=event_items, total=total, limit=limit, offset=offset),
        map=MapEventsResponse(points=map_points, regional_events=map_regionals),
        regions=region_reads,
        raw_messages=RawMessageListResponse(
            items=raw_messages if include_raw_messages else [],
            total=raw_total if include_raw_messages else 0,
            limit=raw_limit if include_raw_messages else 0,
        ),
        pipeline=PipelineSummary(
            raw_messages_total=raw_total if include_pipeline else 0,
            recent_raw_messages=len(raw_messages) if include_pipeline else 0,
            recent_structured_messages=recent_structured,
            recent_mapped_messages=recent_mapped,
            recent_unmatched_messages=recent_unmatched,
            active_feed_events=total if include_pipeline else 0,
            active_map_points=len(map_points) if include_pipeline else 0,
        ),
    )
