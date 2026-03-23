from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name_ar: str
    name_en: str | None = None
    alt_names: list[str] = Field(default_factory=list)
    district: str | None = None
    governorate: str | None = None
    latitude: float
    longitude: float
