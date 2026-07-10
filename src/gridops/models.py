"""SQLAlchemy models for persisted GridOps operational storage."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
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
    Text,
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


class QualityRun(Base):
    """Track one quality evaluation run for a dataset."""

    __tablename__ = "quality_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name="quality_runs_status_valid",
        ),
        CheckConstraint(
            "checked_window_start_utc IS NULL OR checked_window_end_utc IS NULL "
            "OR checked_window_start_utc < checked_window_end_utc",
            name="quality_runs_checked_window_order_valid",
        ),
        Index("ix_quality_runs_dataset_name", "dataset_name"),
        Index("ix_quality_runs_status", "status"),
        Index("ix_quality_runs_started_at_utc", "started_at_utc"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    dataset_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checked_window_start_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checked_window_end_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safe_error_detail: Mapped[str | None] = mapped_column(String(1000))

    results: Mapped[list["QualityResult"]] = relationship(back_populates="quality_run")


class QualityResult(Base):
    """Persist one quality check result without raw payloads or secrets."""

    __tablename__ = "quality_results"
    __table_args__ = (
        CheckConstraint(
            "check_category IN ("
            "'schema', 'completeness', 'continuity', 'uniqueness', 'range', "
            "'freshness', 'timestamp', 'dst', 'source_metadata'"
            ")",
            name="quality_results_check_category_valid",
        ),
        CheckConstraint(
            "severity IN ('info', 'warning', 'error', 'critical')",
            name="quality_results_severity_valid",
        ),
        CheckConstraint(
            "status IN ('passed', 'failed', 'skipped', 'error')",
            name="quality_results_status_valid",
        ),
        CheckConstraint(
            "affected_record_count IS NULL OR affected_record_count >= 0",
            name="quality_results_affected_record_count_nonnegative",
        ),
        Index("ix_quality_results_quality_run_id", "quality_run_id"),
        Index("ix_quality_results_dataset_name", "dataset_name"),
        Index("ix_quality_results_check_name", "check_name"),
        Index("ix_quality_results_severity", "severity"),
        Index("ix_quality_results_status", "status"),
        Index("ix_quality_results_created_at_utc", "created_at_utc"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    quality_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("quality_runs.id"),
        nullable=False,
    )
    dataset_name: Mapped[str] = mapped_column(String(128), nullable=False)
    check_name: Mapped[str] = mapped_column(String(128), nullable=False)
    check_category: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    observed_value: Mapped[str | None] = mapped_column(Text)
    expected_value: Mapped[str | None] = mapped_column(Text)
    affected_record_count: Mapped[int | None] = mapped_column(BigInteger)
    safe_detail: Mapped[str | None] = mapped_column(String(1000))
    is_blocking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    related_ingestion_run_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("ingestion_runs.id"),
    )
    related_raw_snapshot_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("raw_snapshots.id"),
    )
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    quality_run: Mapped[QualityRun] = relationship(back_populates="results")


class ForecastIssue(Base):
    """Persist one deterministic M04 forecast issue definition."""

    __tablename__ = "forecast_issues"
    __table_args__ = (
        CheckConstraint("horizon_length_hours > 0", name="forecast_issues_horizon_positive"),
        CheckConstraint(
            "status IN ('defined', 'blocked', 'ready')",
            name="forecast_issues_status_valid",
        ),
        UniqueConstraint(
            "forecast_issue_time_utc",
            "forecast_type",
            "feature_version",
            name="uq_forecast_issues_issue_type_feature_version",
        ),
        Index("ix_forecast_issues_issue_time", "forecast_issue_time_utc"),
        Index("ix_forecast_issues_forecast_type", "forecast_type"),
        Index("ix_forecast_issues_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    forecast_issue_time_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    horizon_length_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    forecast_type: Mapped[str] = mapped_column(String(128), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(128), nullable=False)
    point_in_time_safety_rule: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    quality_blocking_behavior: Mapped[str | None] = mapped_column(String(256))
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FeatureSnapshotRun(Base):
    """Track an M04 feature snapshot generation attempt."""

    __tablename__ = "feature_snapshot_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('planned', 'running', 'succeeded', 'failed', 'blocked')",
            name="feature_snapshot_runs_status_valid",
        ),
        Index("ix_feature_snapshot_runs_forecast_issue_id", "forecast_issue_id"),
        Index("ix_feature_snapshot_runs_status", "status"),
        Index("ix_feature_snapshot_runs_started_at_utc", "started_at_utc"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    forecast_issue_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("forecast_issues.id"),
        nullable=False,
    )
    feature_version: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    quality_status: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safe_error_detail: Mapped[str | None] = mapped_column(String(1000))


class FeatureSnapshotRow(Base):
    """Store one M04 feature-snapshot target row shell and lineage metadata."""

    __tablename__ = "feature_snapshot_rows"
    __table_args__ = (
        CheckConstraint("lead_hour > 0", name="feature_snapshot_rows_lead_hour_positive"),
        CheckConstraint(
            "target_interval_start_utc < target_interval_end_utc",
            name="feature_snapshot_rows_target_interval_order_valid",
        ),
        UniqueConstraint(
            "feature_snapshot_run_id",
            "target_interval_start_utc",
            name="uq_feature_snapshot_rows_run_target_start",
        ),
        Index("ix_feature_snapshot_rows_run_id", "feature_snapshot_run_id"),
        Index("ix_feature_snapshot_rows_target_start", "target_interval_start_utc"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    feature_snapshot_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("feature_snapshot_runs.id"),
        nullable=False,
    )
    forecast_issue_time_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    target_interval_start_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    target_interval_end_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    lead_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    feature_version: Mapped[str] = mapped_column(String(128), nullable=False)
    quality_status: Mapped[str] = mapped_column(String(64), nullable=False)
    demand_source_row_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("ieso_hourly_demand.id"),
    )
    weather_observation_source_row_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("weather_observations.id"),
    )
    weather_forecast_source_row_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("weather_forecasts.id"),
    )
    related_quality_run_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("quality_runs.id"),
    )
    lineage_metadata: Mapped[str | None] = mapped_column(Text)


class BaselineForecastRun(Base):
    """Track one M04 baseline forecast run."""

    __tablename__ = "baseline_forecast_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('planned', 'running', 'succeeded', 'failed', 'blocked')",
            name="baseline_forecast_runs_status_valid",
        ),
        CheckConstraint(
            "training_window_start_utc IS NULL OR training_window_end_utc IS NULL "
            "OR training_window_start_utc < training_window_end_utc",
            name="baseline_forecast_runs_training_window_order_valid",
        ),
        CheckConstraint(
            "evaluation_window_start_utc IS NULL OR evaluation_window_end_utc IS NULL "
            "OR evaluation_window_start_utc < evaluation_window_end_utc",
            name="baseline_forecast_runs_evaluation_window_order_valid",
        ),
        Index("ix_baseline_forecast_runs_baseline_name", "baseline_name"),
        Index("ix_baseline_forecast_runs_status", "status"),
        Index("ix_baseline_forecast_runs_started_at_utc", "started_at_utc"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    baseline_name: Mapped[str] = mapped_column(String(128), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    training_window_start_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    training_window_end_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evaluation_window_start_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evaluation_window_end_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quality_blocking_behavior: Mapped[str | None] = mapped_column(String(256))
    run_metadata: Mapped[str | None] = mapped_column(Text)
    started_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safe_error_detail: Mapped[str | None] = mapped_column(String(1000))


class BaselineForecastPrediction(Base):
    """Store one M04 baseline prediction row."""

    __tablename__ = "baseline_forecast_predictions"
    __table_args__ = (
        CheckConstraint("lead_hour > 0", name="baseline_forecast_predictions_lead_hour_positive"),
        CheckConstraint(
            "target_interval_start_utc < target_interval_end_utc",
            name="baseline_forecast_predictions_target_interval_order_valid",
        ),
        UniqueConstraint(
            "baseline_forecast_run_id",
            "forecast_issue_time_utc",
            "target_interval_start_utc",
            name="uq_baseline_predictions_run_issue_target",
        ),
        Index("ix_baseline_predictions_run_id", "baseline_forecast_run_id"),
        Index("ix_baseline_predictions_issue_time", "forecast_issue_time_utc"),
        Index("ix_baseline_predictions_target_start", "target_interval_start_utc"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    baseline_forecast_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("baseline_forecast_runs.id"),
        nullable=False,
    )
    feature_snapshot_row_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("feature_snapshot_rows.id"),
    )
    forecast_issue_time_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    target_interval_start_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    target_interval_end_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    lead_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_demand_mw: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    actual_demand_mw: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    prediction_status: Mapped[str] = mapped_column(String(32), nullable=False)
    lineage_metadata: Mapped[str | None] = mapped_column(Text)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BaselineMetricResult(Base):
    """Store aggregate M04 baseline metric values."""

    __tablename__ = "baseline_metric_results"
    __table_args__ = (
        UniqueConstraint(
            "baseline_forecast_run_id",
            "metric_name",
            name="uq_baseline_metric_results_run_metric",
        ),
        Index("ix_baseline_metric_results_run_id", "baseline_forecast_run_id"),
        Index("ix_baseline_metric_results_metric_name", "metric_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    baseline_forecast_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("baseline_forecast_runs.id"),
        nullable=False,
    )
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    metric_unit: Mapped[str | None] = mapped_column(String(64))
    evaluation_window_start_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evaluation_window_end_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lineage_metadata: Mapped[str | None] = mapped_column(Text)


class BaselineSliceMetricResult(Base):
    """Store M04 baseline metric values for one evaluation slice."""

    __tablename__ = "baseline_slice_metric_results"
    __table_args__ = (
        UniqueConstraint(
            "baseline_forecast_run_id",
            "slice_name",
            "slice_value",
            "metric_name",
            name="uq_baseline_slice_metric_results_run_slice_metric",
        ),
        Index("ix_baseline_slice_metric_results_run_id", "baseline_forecast_run_id"),
        Index("ix_baseline_slice_metric_results_slice", "slice_name", "slice_value"),
        Index("ix_baseline_slice_metric_results_metric_name", "metric_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    baseline_forecast_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("baseline_forecast_runs.id"),
        nullable=False,
    )
    slice_name: Mapped[str] = mapped_column(String(128), nullable=False)
    slice_value: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    metric_unit: Mapped[str | None] = mapped_column(String(64))
    row_count: Mapped[int | None] = mapped_column(BigInteger)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lineage_metadata: Mapped[str | None] = mapped_column(Text)


class ModelTrainingRun(Base):
    """Track one M05 production-candidate training attempt."""

    __tablename__ = "model_training_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('planned', 'running', 'succeeded', 'failed', 'blocked')",
            name="model_training_runs_status_valid",
        ),
        CheckConstraint(
            "training_window_start_utc < training_window_end_utc",
            name="model_training_runs_training_window_order_valid",
        ),
        CheckConstraint(
            "evaluation_window_start_utc < evaluation_window_end_utc",
            name="model_training_runs_evaluation_window_order_valid",
        ),
        Index("ix_model_training_runs_model_name", "model_name"),
        Index("ix_model_training_runs_model_version", "model_version"),
        Index("ix_model_training_runs_status", "status"),
        Index("ix_model_training_runs_started_at_utc", "started_at_utc"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_type: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    training_window_start_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    training_window_end_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    evaluation_window_start_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    evaluation_window_end_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    parameters_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    metrics_summary_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    lineage_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON)
    started_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    safe_error_detail: Mapped[str | None] = mapped_column(String(1000))


class ModelArtifact(Base):
    """Record metadata for a persisted M05 candidate model artifact."""

    __tablename__ = "model_artifacts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'available', 'failed', 'deprecated')",
            name="model_artifacts_status_valid",
        ),
        CheckConstraint(
            "training_window_start_utc < training_window_end_utc",
            name="model_artifacts_training_window_order_valid",
        ),
        CheckConstraint(
            "evaluation_window_start_utc < evaluation_window_end_utc",
            name="model_artifacts_evaluation_window_order_valid",
        ),
        UniqueConstraint("artifact_hash", name="uq_model_artifacts_artifact_hash"),
        Index("ix_model_artifacts_training_run_id", "model_training_run_id"),
        Index("ix_model_artifacts_model_name", "model_name"),
        Index("ix_model_artifacts_model_version", "model_version"),
        Index("ix_model_artifacts_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    model_training_run_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("model_training_runs.id"),
    )
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_type: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(128), nullable=False)
    artifact_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    artifact_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    training_window_start_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    training_window_end_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    evaluation_window_start_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    evaluation_window_end_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    parameters_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    metrics_summary_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    lineage_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ModelSelectionResult(Base):
    """Persist one explicit model-selection gate result."""

    __tablename__ = "model_selection_results"
    __table_args__ = (
        CheckConstraint(
            "selection_status IN ('evaluated', 'selected', 'rejected', 'failed')",
            name="model_selection_results_status_valid",
        ),
        CheckConstraint(
            "training_window_start_utc < training_window_end_utc",
            name="model_selection_results_training_window_order_valid",
        ),
        CheckConstraint(
            "evaluation_window_start_utc < evaluation_window_end_utc",
            name="model_selection_results_evaluation_window_order_valid",
        ),
        Index("ix_model_selection_results_training_run_id", "model_training_run_id"),
        Index("ix_model_selection_results_artifact_id", "model_artifact_id"),
        Index("ix_model_selection_results_status", "selection_status"),
        Index("ix_model_selection_results_created_at_utc", "created_at_utc"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    model_training_run_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("model_training_runs.id"),
    )
    model_artifact_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("model_artifacts.id"),
    )
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_type: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(128), nullable=False)
    selection_status: Mapped[str] = mapped_column(String(32), nullable=False)
    selection_reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    training_window_start_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    training_window_end_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    evaluation_window_start_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    evaluation_window_end_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    candidate_metrics_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    baseline_metrics_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    lineage_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProductionForecastRun(Base):
    """Track one M05 production forecast generation attempt."""

    __tablename__ = "production_forecast_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('planned', 'running', 'succeeded', 'failed', 'blocked')",
            name="production_forecast_runs_status_valid",
        ),
        Index("ix_production_forecast_runs_artifact_id", "model_artifact_id"),
        Index("ix_production_forecast_runs_feature_snapshot_run_id", "feature_snapshot_run_id"),
        Index("ix_production_forecast_runs_issue_time", "forecast_issue_time_utc"),
        Index("ix_production_forecast_runs_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    model_artifact_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("model_artifacts.id"),
    )
    feature_snapshot_run_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("feature_snapshot_runs.id"),
    )
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_type: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(128), nullable=False)
    forecast_issue_time_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    quality_status: Mapped[str | None] = mapped_column(String(64))
    lineage_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON)
    started_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    safe_error_detail: Mapped[str | None] = mapped_column(String(1000))


class ProductionForecastPrediction(Base):
    """Store one M05 production forecast prediction row."""

    __tablename__ = "production_forecast_predictions"
    __table_args__ = (
        CheckConstraint(
            "target_interval_start_utc < target_interval_end_utc",
            name="production_forecast_predictions_target_interval_order_valid",
        ),
        CheckConstraint(
            "lead_hour > 0",
            name="production_forecast_predictions_lead_hour_positive",
        ),
        CheckConstraint(
            "p50_demand_mw IS NOT NULL OR point_forecast_demand_mw IS NOT NULL",
            name="production_forecast_predictions_point_or_p50_required",
        ),
        CheckConstraint(
            "p10_demand_mw IS NULL OR p50_demand_mw IS NULL OR p10_demand_mw <= p50_demand_mw",
            name="production_forecast_predictions_p10_not_above_p50",
        ),
        CheckConstraint(
            "p90_demand_mw IS NULL OR p50_demand_mw IS NULL OR p90_demand_mw >= p50_demand_mw",
            name="production_forecast_predictions_p90_not_below_p50",
        ),
        UniqueConstraint(
            "production_forecast_run_id",
            "forecast_issue_time_utc",
            "target_interval_start_utc",
            name="uq_production_forecast_predictions_run_issue_target",
        ),
        Index("ix_production_forecast_predictions_run_id", "production_forecast_run_id"),
        Index("ix_production_forecast_predictions_issue_time", "forecast_issue_time_utc"),
        Index("ix_production_forecast_predictions_target_start", "target_interval_start_utc"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    production_forecast_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("production_forecast_runs.id"),
        nullable=False,
    )
    feature_snapshot_row_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("feature_snapshot_rows.id"),
    )
    forecast_issue_time_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    target_interval_start_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    target_interval_end_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    lead_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    p10_demand_mw: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    p50_demand_mw: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    p90_demand_mw: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    point_forecast_demand_mw: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    prediction_type: Mapped[str] = mapped_column(String(64), nullable=False)
    lineage_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ForecastPeakOutput(Base):
    """Store peak-demand summary output for one production forecast run."""

    __tablename__ = "forecast_peak_outputs"
    __table_args__ = (
        CheckConstraint(
            "peak_target_interval_start_utc < peak_target_interval_end_utc",
            name="forecast_peak_outputs_peak_interval_order_valid",
        ),
        CheckConstraint("peak_lead_hour > 0", name="forecast_peak_outputs_lead_hour_positive"),
        CheckConstraint(
            "peak_demand_mw >= 0",
            name="forecast_peak_outputs_peak_demand_nonnegative",
        ),
        UniqueConstraint("production_forecast_run_id", name="uq_forecast_peak_outputs_run_id"),
        Index("ix_forecast_peak_outputs_run_id", "production_forecast_run_id"),
        Index("ix_forecast_peak_outputs_peak_start", "peak_target_interval_start_utc"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    production_forecast_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("production_forecast_runs.id"),
        nullable=False,
    )
    peak_target_interval_start_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    peak_target_interval_end_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    peak_demand_mw: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    peak_lead_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    lineage_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ForecastRampOutput(Base):
    """Store ramp summary output for one forecast target interval."""

    __tablename__ = "forecast_ramp_outputs"
    __table_args__ = (
        CheckConstraint(
            "previous_target_interval_start_utc < target_interval_start_utc",
            name="forecast_ramp_outputs_previous_before_target",
        ),
        CheckConstraint(
            "absolute_ramp_mw >= 0",
            name="forecast_ramp_outputs_absolute_ramp_nonnegative",
        ),
        UniqueConstraint(
            "production_forecast_run_id",
            "target_interval_start_utc",
            name="uq_forecast_ramp_outputs_run_target",
        ),
        Index("ix_forecast_ramp_outputs_run_id", "production_forecast_run_id"),
        Index("ix_forecast_ramp_outputs_target_start", "target_interval_start_utc"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    production_forecast_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("production_forecast_runs.id"),
        nullable=False,
    )
    target_interval_start_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    previous_target_interval_start_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    forecast_ramp_mw: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    absolute_ramp_mw: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    lineage_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ModelPerformanceSummary(Base):
    """Store deterministic actual-vs-forecast performance summaries."""

    __tablename__ = "model_performance_summaries"
    __table_args__ = (
        CheckConstraint(
            "evaluation_window_start_utc < evaluation_window_end_utc",
            name="model_performance_summaries_evaluation_window_order_valid",
        ),
        CheckConstraint("row_count >= 0", name="model_performance_summaries_row_count_nonnegative"),
        UniqueConstraint(
            "model_artifact_id",
            "metric_name",
            "evaluation_window_start_utc",
            "evaluation_window_end_utc",
            name="uq_model_performance_summaries_artifact_metric_window",
        ),
        Index("ix_model_performance_summaries_artifact_id", "model_artifact_id"),
        Index("ix_model_performance_summaries_metric_name", "metric_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    model_artifact_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("model_artifacts.id"),
    )
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_type: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    metric_unit: Mapped[str | None] = mapped_column(String(64))
    row_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    evaluation_window_start_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    evaluation_window_end_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    lineage_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ModelDriftSummary(Base):
    """Store deterministic feature or prediction drift summaries."""

    __tablename__ = "model_drift_summaries"
    __table_args__ = (
        CheckConstraint(
            "baseline_window_start_utc < baseline_window_end_utc",
            name="model_drift_summaries_baseline_window_order_valid",
        ),
        CheckConstraint(
            "comparison_window_start_utc < comparison_window_end_utc",
            name="model_drift_summaries_comparison_window_order_valid",
        ),
        CheckConstraint(
            "drift_score IS NULL OR drift_score >= 0",
            name="model_drift_summaries_drift_score_nonnegative",
        ),
        Index("ix_model_drift_summaries_artifact_id", "model_artifact_id"),
        Index("ix_model_drift_summaries_feature_name", "feature_name"),
        Index("ix_model_drift_summaries_created_at_utc", "created_at_utc"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    model_artifact_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("model_artifacts.id"),
    )
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_type: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(128), nullable=False)
    feature_name: Mapped[str] = mapped_column(String(128), nullable=False)
    drift_metric_name: Mapped[str] = mapped_column(String(128), nullable=False)
    drift_score: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    baseline_window_start_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    baseline_window_end_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    comparison_window_start_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    comparison_window_end_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    summary_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    lineage_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
