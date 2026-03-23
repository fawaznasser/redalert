from __future__ import annotations

from datetime import datetime

from app.schemas.common import ApiModel
from app.schemas.events import EventListResponse, MapEventsResponse
from app.schemas.raw_messages import RawMessageListResponse
from app.schemas.regions import RegionRead
from app.schemas.stats import StatsResponse


class PipelineSummary(ApiModel):
    raw_messages_total: int
    recent_raw_messages: int
    recent_structured_messages: int
    recent_mapped_messages: int
    recent_unmatched_messages: int
    active_feed_events: int
    active_map_points: int


class DashboardResponse(ApiModel):
    snapshot_at: datetime
    stats: StatsResponse
    events: EventListResponse
    map: MapEventsResponse
    regions: list[RegionRead]
    raw_messages: RawMessageListResponse
    pipeline: PipelineSummary
