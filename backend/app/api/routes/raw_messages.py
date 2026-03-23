from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.raw_messages import RawMessageListResponse
from app.services.raw_message_service import list_recent_raw_messages

router = APIRouter(tags=["raw-messages"])


@router.get("/raw-messages/recent", response_model=RawMessageListResponse)
def get_recent_raw_messages(
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> RawMessageListResponse:
    total, items = list_recent_raw_messages(db, limit=limit)
    return RawMessageListResponse(items=items, total=total, limit=limit)
