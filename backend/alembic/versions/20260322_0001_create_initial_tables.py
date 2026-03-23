from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260322_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "raw_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("telegram_message_id", sa.String(length=128), nullable=True),
        sa.Column("channel_name", sa.String(length=255), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("message_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_raw_messages_channel_name", "raw_messages", ["channel_name"])
    op.create_index("ix_raw_messages_telegram_message_id", "raw_messages", ["telegram_message_id"])

    op.create_table(
        "locations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name_ar", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=True),
        sa.Column("alt_names", sa.Text(), nullable=True),
        sa.Column("district", sa.String(length=255), nullable=True),
        sa.Column("governorate", sa.String(length=255), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name_ar"),
    )
    op.create_index("ix_locations_name_ar", "locations", ["name_ar"])

    op.create_table(
        "regions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("geojson", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_regions_slug", "regions", ["slug"])

    op.create_table(
        "events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("raw_message_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("location_id", sa.String(length=36), nullable=True),
        sa.Column("region_id", sa.String(length=36), nullable=True),
        sa.Column("location_mode", sa.String(length=32), nullable=False),
        sa.Column("is_precise", sa.Boolean(), nullable=False),
        sa.Column("location_name_raw", sa.String(length=255), nullable=True),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["raw_message_id"], ["raw_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["region_id"], ["regions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_event_time", "events", ["event_time"])
    op.create_index("ix_events_event_type", "events", ["event_type"])
    op.create_index("ix_events_location_id", "events", ["location_id"])
    op.create_index("ix_events_location_mode", "events", ["location_mode"])
    op.create_index("ix_events_region_id", "events", ["region_id"])


def downgrade() -> None:
    op.drop_index("ix_events_region_id", table_name="events")
    op.drop_index("ix_events_location_mode", table_name="events")
    op.drop_index("ix_events_location_id", table_name="events")
    op.drop_index("ix_events_event_type", table_name="events")
    op.drop_index("ix_events_event_time", table_name="events")
    op.drop_table("events")

    op.drop_index("ix_regions_slug", table_name="regions")
    op.drop_table("regions")

    op.drop_index("ix_locations_name_ar", table_name="locations")
    op.drop_table("locations")

    op.drop_index("ix_raw_messages_telegram_message_id", table_name="raw_messages")
    op.drop_index("ix_raw_messages_channel_name", table_name="raw_messages")
    op.drop_table("raw_messages")
