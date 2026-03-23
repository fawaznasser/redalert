from __future__ import annotations

from uuid import uuid4

from sqlalchemy import Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    geoname_id: Mapped[int | None] = mapped_column(index=True, unique=True)
    source: Mapped[str] = mapped_column(String(64), default="manual", index=True)
    feature_class: Mapped[str | None] = mapped_column(String(8))
    feature_code: Mapped[str | None] = mapped_column(String(16))
    name_ar: Mapped[str] = mapped_column(String(255), index=True)
    name_en: Mapped[str | None] = mapped_column(String(255))
    alt_names: Mapped[str | None] = mapped_column(Text)
    district: Mapped[str | None] = mapped_column(String(255))
    governorate: Mapped[str | None] = mapped_column(String(255))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)

    events: Mapped[list["Event"]] = relationship(back_populates="location")
