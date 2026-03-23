from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def healthcheck(db: Session = Depends(get_db)) -> HealthResponse:
    database_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database_status = "error"

    status = "ok" if database_status == "ok" else "degraded"
    telegram_status = "enabled" if settings.telegram_is_configured else "disabled"
    return HealthResponse(status=status, database=database_status, telegram_listener=telegram_status)
