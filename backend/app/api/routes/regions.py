from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.region import Region
from app.schemas.regions import RegionRead

router = APIRouter(tags=["regions"])


@router.get("/regions", response_model=list[RegionRead])
def get_regions(db: Session = Depends(get_db)) -> list[RegionRead]:
    regions = db.scalars(select(Region).order_by(Region.name.asc())).all()
    return [
        RegionRead(
            id=region.id,
            slug=region.slug,
            name=region.name,
            geojson=json.loads(region.geojson),
        )
        for region in regions
    ]
