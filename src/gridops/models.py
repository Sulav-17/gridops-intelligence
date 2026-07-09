"""SQLAlchemy models for M02 ingestion storage."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gridops.database import Base


class IngestionRun(Base):
    """Track one attempted ingestion operation."""

    __tablename__ = "ingestion_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name="ingestion_runs_status_valid",
        ),
        CheckConstraint("records_seen >= 0", name="ingestion_runs_records_seen_nonnegative"),
        CheckConstraint("records_loaded >= 0", name="ingestion_runs_records_loaded_nonnegative"),
        Index("ix_ingestion_runs_source_name", "source_name"),
        Index("ix_ingestion_runs_status", "status"),
        Index("ix_ingestion_runs_started_at_utc", "started_at_utc"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_type: Mapped[str | None] = mapped_column(String(128))
    error_message: Mapped[str | None] = mapped_column(String(1000))
    records_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_loaded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    raw_snapshots: Mapped[list["RawSnapshot"]] = relationship(back_populates="ingestion_run")


class RawSnapshot(Base):
    """Persist immutable source payload evidence and retrieval metadata."""

    __tablename__ = "raw_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "source_name",
            "content_hash_sha256",
            name="uq_raw_snapshots_source_name_content_hash_sha256",
        ),
        CheckConstraint("byte_size >= 0", name="raw_snapshots_byte_size_nonnegative"),
        Index("ix_raw_snapshots_source_name", "source_name"),
        Index("ix_raw_snapshots_retrieved_at_utc", "retrieved_at_utc"),
        Index("ix_raw_snapshots_content_hash_sha256", "content_hash_sha256"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    retrieval_identifier: Mapped[str | None] = mapped_column(String(512))
    source_url: Mapped[str | None] = mapped_column(String(2048))
    retrieved_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ingestion_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("ingestion_runs.id"),
        nullable=False,
    )

    ingestion_run: Mapped[IngestionRun] = relationship(back_populates="raw_snapshots")


class IesoHourlyDemand(Base):
    """Silver IESO hourly demand fact traceable to raw evidence."""

    __tablename__ = "ieso_hourly_demand"
    __table_args__ = (
        CheckConstraint(
            "source_hour_ending BETWEEN 1 AND 24",
            name="ieso_hourly_demand_hour_ending_valid",
        ),
        CheckConstraint("demand_mw >= 0", name="ieso_hourly_demand_demand_mw_nonnegative"),
        UniqueConstraint(
            "source_service_date",
            "source_hour_ending",
            "row_hash_sha256",
            name="uq_ieso_hourly_demand_source_key_row_hash",
        ),
        Index("ix_ieso_hourly_demand_interval_end_utc", "interval_end_utc"),
        Index(
            "uq_ieso_hourly_demand_current_source_key",
            "source_service_date",
            "source_hour_ending",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source_service_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_hour_ending: Mapped[int] = mapped_column(Integer, nullable=False)
    interval_start_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    interval_end_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    demand_mw: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    source_snapshot_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("raw_snapshots.id"),
        nullable=False,
    )
    ingestion_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("ingestion_runs.id"),
        nullable=False,
    )
    row_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    superseded_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WeatherObservation(Base):
    """Silver weather observation fact traceable to raw evidence."""

    __tablename__ = "weather_observations"
    __table_args__ = (
        UniqueConstraint(
            "source_name",
            "source_station_id",
            "observed_at_utc",
            "row_hash_sha256",
            name="uq_weather_observations_source_key_row_hash",
        ),
        Index("ix_weather_observations_observed_at_utc", "observed_at_utc"),
        Index("ix_weather_observations_station_time", "source_station_id", "observed_at_utc"),
        Index(
            "uq_weather_observations_current_source_key",
            "source_name",
            "source_station_id",
            "observed_at_utc",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_station_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_native_timestamp: Mapped[str] = mapped_column(String(128), nullable=False)
    observed_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    relative_humidity_percent: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    wind_speed_kph: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    precipitation_mm: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    source_snapshot_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("raw_snapshots.id"),
        nullable=False,
    )
    ingestion_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("ingestion_runs.id"),
        nullable=False,
    )
    row_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    superseded_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WeatherForecast(Base):
    """Silver archived weather forecast fact traceable to raw evidence."""

    __tablename__ = "weather_forecasts"
    __table_args__ = (
        UniqueConstraint(
            "source_name",
            "forecast_location",
            "issue_time_utc",
            "valid_time_utc",
            "variable_name",
            "row_hash_sha256",
            name="uq_weather_forecasts_source_key_row_hash",
        ),
        Index("ix_weather_forecasts_issue_time_utc", "issue_time_utc"),
        Index("ix_weather_forecasts_valid_time_utc", "valid_time_utc"),
        Index(
            "ix_weather_forecasts_location_valid_time",
            "forecast_location",
            "valid_time_utc",
        ),
        Index(
            "uq_weather_forecasts_current_source_key",
            "source_name",
            "forecast_location",
            "issue_time_utc",
            "valid_time_utc",
            "variable_name",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)
    forecast_location: Mapped[str] = mapped_column(String(128), nullable=False)
    source_native_issue_time: Mapped[str] = mapped_column(String(128), nullable=False)
    source_native_valid_time: Mapped[str] = mapped_column(String(128), nullable=False)
    issue_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lead_time_hours: Mapped[int | None] = mapped_column(Integer)
    variable_name: Mapped[str] = mapped_column(String(128), nullable=False)
    variable_value: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    variable_unit: Mapped[str | None] = mapped_column(String(64))
    source_snapshot_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("raw_snapshots.id"),
        nullable=False,
    )
    ingestion_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("ingestion_runs.id"),
        nullable=False,
    )
    row_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    superseded_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
