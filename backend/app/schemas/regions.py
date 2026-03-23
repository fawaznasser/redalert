from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class RegionRead(BaseModel):
    id: str
    slug: str
    name: str
    geojson: dict[str, Any]
