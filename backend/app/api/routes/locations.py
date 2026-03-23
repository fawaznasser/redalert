from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.location import Location
from app.schemas.locations import LocationRead

router = APIRouter(tags=["locations"])


def _alt_names(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


@router.get("/locations", response_model=list[LocationRead])
def get_locations(db: Session = Depends(get_db)) -> list[LocationRead]:
    locations = db.scalars(select(Location).order_by(Location.name_ar.asc())).all()
    return [
        LocationRead(
            id=location.id,
            name_ar=location.name_ar,
            name_en=location.name_en,
            alt_names=_alt_names(location.alt_names),
            district=location.district,
            governorate=location.governorate,
            latitude=location.latitude,
            longitude=location.longitude,
        )
        for location in locations
    ]
