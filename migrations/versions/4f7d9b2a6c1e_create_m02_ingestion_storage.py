"""Create M02 ingestion storage.

Revision ID: 4f7d9b2a6c1e
Revises: 9c3a87779a9e
Create Date: 2026-07-08

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4f7d9b2a6c1e"
down_revision: str | Sequence[str] | None = "9c3a87779a9e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply M02 ingestion storage tables."""

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("source_name", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_type", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("records_seen", sa.Integer(), nullable=False),
        sa.Column("records_loaded", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "records_loaded >= 0",
            name=op.f("ck_ingestion_runs_ingestion_runs_records_loaded_nonnegative"),
        ),
        sa.CheckConstraint(
            "records_seen >= 0",
            name=op.f("ck_ingestion_runs_ingestion_runs_records_seen_nonnegative"),
        ),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name=op.f("ck_ingestion_runs_ingestion_runs_status_valid"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingestion_runs")),
    )
    op.create_index(
        "ix_ingestion_runs_source_name",
        "ingestion_runs",
        ["source_name"],
        unique=False,
    )
    op.create_index("ix_ingestion_runs_started_at_utc", "ingestion_runs", ["started_at_utc"])
    op.create_index("ix_ingestion_runs_status", "ingestion_runs", ["status"])

    op.create_table(
        "raw_snapshots",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("source_name", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("retrieval_identifier", sa.String(length=512), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("retrieved_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("ingestion_run_id", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "byte_size >= 0",
            name=op.f("ck_raw_snapshots_raw_snapshots_byte_size_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_runs.id"],
            name=op.f("fk_raw_snapshots_ingestion_run_id_ingestion_runs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_raw_snapshots")),
        sa.UniqueConstraint(
            "source_name",
            "content_hash_sha256",
            name="uq_raw_snapshots_source_name_content_hash_sha256",
        ),
    )
    op.create_index(
        "ix_raw_snapshots_content_hash_sha256",
        "raw_snapshots",
        ["content_hash_sha256"],
    )
    op.create_index("ix_raw_snapshots_retrieved_at_utc", "raw_snapshots", ["retrieved_at_utc"])
    op.create_index("ix_raw_snapshots_source_name", "raw_snapshots", ["source_name"])

    op.create_table(
        "ieso_hourly_demand",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("source_service_date", sa.Date(), nullable=False),
        sa.Column("source_hour_ending", sa.Integer(), nullable=False),
        sa.Column("interval_start_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("interval_end_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("demand_mw", sa.Numeric(12, 3), nullable=False),
        sa.Column("source_snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("ingestion_run_id", sa.BigInteger(), nullable=False),
        sa.Column("row_hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("superseded_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "demand_mw >= 0",
            name=op.f("ck_ieso_hourly_demand_ieso_hourly_demand_demand_mw_nonnegative"),
        ),
        sa.CheckConstraint(
            "source_hour_ending BETWEEN 1 AND 24",
            name=op.f("ck_ieso_hourly_demand_ieso_hourly_demand_hour_ending_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_runs.id"],
            name=op.f("fk_ieso_hourly_demand_ingestion_run_id_ingestion_runs"),
        ),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"],
            ["raw_snapshots.id"],
            name=op.f("fk_ieso_hourly_demand_source_snapshot_id_raw_snapshots"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ieso_hourly_demand")),
        sa.UniqueConstraint(
            "source_service_date",
            "source_hour_ending",
            "row_hash_sha256",
            name="uq_ieso_hourly_demand_source_key_row_hash",
        ),
    )
    op.create_index(
        "ix_ieso_hourly_demand_interval_end_utc",
        "ieso_hourly_demand",
        ["interval_end_utc"],
    )
    op.create_index(
        "uq_ieso_hourly_demand_current_source_key",
        "ieso_hourly_demand",
        ["source_service_date", "source_hour_ending"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )

    op.create_table(
        "weather_observations",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("source_name", sa.String(length=128), nullable=False),
        sa.Column("source_station_id", sa.String(length=128), nullable=False),
        sa.Column("source_native_timestamp", sa.String(length=128), nullable=False),
        sa.Column("observed_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("temperature_c", sa.Numeric(8, 3), nullable=True),
        sa.Column("relative_humidity_percent", sa.Numeric(6, 3), nullable=True),
        sa.Column("wind_speed_kph", sa.Numeric(8, 3), nullable=True),
        sa.Column("precipitation_mm", sa.Numeric(8, 3), nullable=True),
        sa.Column("source_snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("ingestion_run_id", sa.BigInteger(), nullable=False),
        sa.Column("row_hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("superseded_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_runs.id"],
            name=op.f("fk_weather_observations_ingestion_run_id_ingestion_runs"),
        ),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"],
            ["raw_snapshots.id"],
            name=op.f("fk_weather_observations_source_snapshot_id_raw_snapshots"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_weather_observations")),
        sa.UniqueConstraint(
            "source_name",
            "source_station_id",
            "observed_at_utc",
            "row_hash_sha256",
            name="uq_weather_observations_source_key_row_hash",
        ),
    )
    op.create_index(
        "ix_weather_observations_observed_at_utc",
        "weather_observations",
        ["observed_at_utc"],
    )
    op.create_index(
        "ix_weather_observations_station_time",
        "weather_observations",
        ["source_station_id", "observed_at_utc"],
    )
    op.create_index(
        "uq_weather_observations_current_source_key",
        "weather_observations",
        ["source_name", "source_station_id", "observed_at_utc"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )

    op.create_table(
        "weather_forecasts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("source_name", sa.String(length=128), nullable=False),
        sa.Column("forecast_location", sa.String(length=128), nullable=False),
        sa.Column("source_native_issue_time", sa.String(length=128), nullable=False),
        sa.Column("source_native_valid_time", sa.String(length=128), nullable=False),
        sa.Column("issue_time_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_time_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lead_time_hours", sa.Integer(), nullable=True),
        sa.Column("variable_name", sa.String(length=128), nullable=False),
        sa.Column("variable_value", sa.Numeric(12, 3), nullable=False),
        sa.Column("variable_unit", sa.String(length=64), nullable=True),
        sa.Column("source_snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("ingestion_run_id", sa.BigInteger(), nullable=False),
        sa.Column("row_hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("superseded_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_runs.id"],
            name=op.f("fk_weather_forecasts_ingestion_run_id_ingestion_runs"),
        ),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"],
            ["raw_snapshots.id"],
            name=op.f("fk_weather_forecasts_source_snapshot_id_raw_snapshots"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_weather_forecasts")),
        sa.UniqueConstraint(
            "source_name",
            "forecast_location",
            "issue_time_utc",
            "valid_time_utc",
            "variable_name",
            "row_hash_sha256",
            name="uq_weather_forecasts_source_key_row_hash",
        ),
    )
    op.create_index(
        "ix_weather_forecasts_issue_time_utc",
        "weather_forecasts",
        ["issue_time_utc"],
    )
    op.create_index(
        "ix_weather_forecasts_location_valid_time",
        "weather_forecasts",
        ["forecast_location", "valid_time_utc"],
    )
    op.create_index(
        "ix_weather_forecasts_valid_time_utc",
        "weather_forecasts",
        ["valid_time_utc"],
    )
    op.create_index(
        "uq_weather_forecasts_current_source_key",
        "weather_forecasts",
        ["source_name", "forecast_location", "issue_time_utc", "valid_time_utc", "variable_name"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )


def downgrade() -> None:
    """Revert M02 ingestion storage tables."""

    op.drop_table("weather_forecasts")
    op.drop_table("weather_observations")
    op.drop_table("ieso_hourly_demand")
    op.drop_table("raw_snapshots")
    op.drop_table("ingestion_runs")
