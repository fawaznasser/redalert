from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    raw_message_id: Mapped[str] = mapped_column(ForeignKey("raw_messages.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    location_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"), index=True)
    region_id: Mapped[str | None] = mapped_column(ForeignKey("regions.id"), index=True)
    location_mode: Mapped[str] = mapped_column(String(32), index=True)
    is_precise: Mapped[bool] = mapped_column(Boolean, default=False)
    location_name_raw: Mapped[str | None] = mapped_column(String(255))
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source_text: Mapped[str] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    raw_message: Mapped["RawMessage"] = relationship(back_populates="events")
    location: Mapped["Location | None"] = relationship(back_populates="events")
    region: Mapped["Region | None"] = relationship(back_populates="events")
