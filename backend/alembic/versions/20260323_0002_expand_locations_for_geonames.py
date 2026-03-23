from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260323_0002"
down_revision = "20260322_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.exec_driver_sql("PRAGMA foreign_keys=OFF")

    op.create_table(
        "locations_new",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("geoname_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="manual"),
        sa.Column("feature_class", sa.String(length=8), nullable=True),
        sa.Column("feature_code", sa.String(length=16), nullable=True),
        sa.Column("name_ar", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=True),
        sa.Column("alt_names", sa.Text(), nullable=True),
        sa.Column("district", sa.String(length=255), nullable=True),
        sa.Column("governorate", sa.String(length=255), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.execute(
        """
        INSERT INTO locations_new (
            id, geoname_id, source, feature_class, feature_code,
            name_ar, name_en, alt_names, district, governorate, latitude, longitude
        )
        SELECT
            id, NULL, 'manual', NULL, NULL,
            name_ar, name_en, alt_names, district, governorate, latitude, longitude
        FROM locations
        """
    )

    op.drop_index("ix_locations_name_ar", table_name="locations")
    op.drop_table("locations")
    op.rename_table("locations_new", "locations")
    op.create_index("ix_locations_geoname_id", "locations", ["geoname_id"], unique=True)
    op.create_index("ix_locations_name_ar", "locations", ["name_ar"])
    op.create_index("ix_locations_source", "locations", ["source"])

    connection.exec_driver_sql("PRAGMA foreign_keys=ON")


def downgrade() -> None:
    raise NotImplementedError(
        "Downgrade is not supported because the expanded Lebanon gazetteer can contain duplicate Arabic names."
    )
