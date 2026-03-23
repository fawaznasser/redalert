from __future__ import annotations

import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.event import Event
from app.schemas.common import EventType, LocationMode
from app.schemas.events import EventListResponse, EventRead, MapEventsResponse, MapPoint, RegionalEventRead
from app.services.event_service import get_map_events, list_events
from app.services.live_updates import live_updates

router = APIRouter(tags=["events"])


def _serialize_event(event: Event) -> EventRead:
    return EventRead(
        id=event.id,
        raw_message_id=event.raw_message_id,
        event_type=EventType(event.event_type),
        location_mode=LocationMode(event.location_mode),
        is_precise=event.is_precise,
        location_id=event.location_id,
        region_id=event.region_id,
        location_name=event.location.name_ar if event.location else None,
        region_slug=event.region.slug if event.region else None,
        region_name=event.region.name if event.region else None,
        event_time=event.event_time,
        source_text=event.source_text,
        latitude=event.latitude,
        longitude=event.longitude,
    )


@router.get("/events", response_model=EventListResponse)
def get_events(
    type: EventType | None = Query(default=None),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    location_mode: LocationMode | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> EventListResponse:
    total, items = list_events(
        db,
        event_type=type,
        from_date=from_,
        to_date=to,
        location_mode=location_mode,
        limit=limit,
        offset=offset,
    )
    return EventListResponse(items=[_serialize_event(event) for event in items], total=total, limit=limit, offset=offset)


@router.get("/events/map", response_model=MapEventsResponse)
def get_events_map(
    type: EventType | None = Query(default=None),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
) -> MapEventsResponse:
    point_events, regional_events = get_map_events(db, event_type=type, from_date=from_, to_date=to)
    return MapEventsResponse(
        points=[
            MapPoint(
                id=event.id,
                event_type=EventType(event.event_type),
                latitude=event.latitude or 0.0,
                longitude=event.longitude or 0.0,
                location_name=event.location.name_ar if event.location else event.location_name_raw,
                event_time=event.event_time,
                source_text=event.source_text,
            )
            for event in point_events
            if event.latitude is not None and event.longitude is not None
        ],
        regional_events=[
            RegionalEventRead(
                id=event.id,
                event_type=EventType(event.event_type),
                region_slug=event.region.slug,
                region_name=event.region.name,
                event_time=event.event_time,
                source_text=event.source_text,
            )
            for event in regional_events
            if event.region is not None
        ],
    )


@router.get("/events/stream")
async def stream_events(request: Request) -> StreamingResponse:
    async def event_stream():
        queue = live_updates.subscribe()
        try:
            yield "retry: 3000\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"data: {payload}\n\n"
                except TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            live_updates.unsubscribe(queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
