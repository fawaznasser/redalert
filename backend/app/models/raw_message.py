from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class RawMessage(Base):
    __tablename__ = "raw_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    telegram_message_id: Mapped[str | None] = mapped_column(String(128), index=True)
    channel_name: Mapped[str] = mapped_column(String(255), index=True)
    message_text: Mapped[str] = mapped_column(Text)
    message_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    raw_json: Mapped[str | None] = mapped_column(Text)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    events: Mapped[list["Event"]] = relationship(back_populates="raw_message", cascade="all, delete-orphan")
