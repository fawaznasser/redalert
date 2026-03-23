from __future__ import annotations

from pydantic import BaseModel


class StatsResponse(BaseModel):
    total_events: int
    drone_count: int
    fighter_count: int
    helicopter_count: int
    exact_count: int
    regional_count: int
    last_24h_total: int
    last_24h_drone_count: int
    last_24h_fighter_count: int
    last_24h_helicopter_count: int
