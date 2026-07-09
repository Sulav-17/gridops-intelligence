"""Typed M03 quality contract definitions."""

from dataclasses import dataclass
from enum import StrEnum


class QualitySeverity(StrEnum):
    """Severity assigned to an individual quality result."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class QualityRunStatus(StrEnum):
    """Lifecycle status for a persisted quality run."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class QualityResultStatus(StrEnum):
    """Evaluation status for a persisted quality result."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class QualityCheckCategory(StrEnum):
    """Supported categories for M03 quality checks."""

    SCHEMA = "schema"
    COMPLETENESS = "completeness"
    CONTINUITY = "continuity"
    UNIQUENESS = "uniqueness"
    RANGE = "range"
    FRESHNESS = "freshness"
    TIMESTAMP = "timestamp"
    DST = "dst"
    SOURCE_METADATA = "source_metadata"


@dataclass(frozen=True, slots=True)
class DatasetQualityContract:
    """Static contract metadata for an existing M02 dataset."""

    dataset_name: str
    table_name: str
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...]
    primary_key_fields: tuple[str, ...]
    timestamp_fields: tuple[str, ...]
    source_native_fields: tuple[str, ...]


DATASET_CONTRACTS: dict[str, DatasetQualityContract] = {
    "ieso_hourly_demand": DatasetQualityContract(
        dataset_name="ieso_hourly_demand",
        table_name="ieso_hourly_demand",
        required_fields=(
            "id",
            "source_service_date",
            "source_hour_ending",
            "interval_start_utc",
            "interval_end_utc",
            "demand_mw",
            "source_snapshot_id",
            "ingestion_run_id",
            "row_hash_sha256",
            "is_current",
        ),
        optional_fields=("superseded_at_utc",),
        primary_key_fields=("source_service_date", "source_hour_ending"),
        timestamp_fields=("interval_start_utc", "interval_end_utc", "superseded_at_utc"),
        source_native_fields=("source_service_date", "source_hour_ending"),
    ),
    "weather_observations": DatasetQualityContract(
        dataset_name="weather_observations",
        table_name="weather_observations",
        required_fields=(
            "id",
            "source_name",
            "source_station_id",
            "source_native_timestamp",
            "observed_at_utc",
            "source_snapshot_id",
            "ingestion_run_id",
            "row_hash_sha256",
            "is_current",
        ),
        optional_fields=(
            "temperature_c",
            "relative_humidity_percent",
            "wind_speed_kph",
            "precipitation_mm",
            "superseded_at_utc",
        ),
        primary_key_fields=("source_name", "source_station_id", "observed_at_utc"),
        timestamp_fields=("observed_at_utc", "superseded_at_utc"),
        source_native_fields=("source_native_timestamp",),
    ),
    "weather_forecasts": DatasetQualityContract(
        dataset_name="weather_forecasts",
        table_name="weather_forecasts",
        required_fields=(
            "id",
            "source_name",
            "forecast_location",
            "source_native_issue_time",
            "source_native_valid_time",
            "issue_time_utc",
            "valid_time_utc",
            "variable_name",
            "variable_value",
            "source_snapshot_id",
            "ingestion_run_id",
            "row_hash_sha256",
            "is_current",
        ),
        optional_fields=("lead_time_hours", "variable_unit", "superseded_at_utc"),
        primary_key_fields=(
            "source_name",
            "forecast_location",
            "issue_time_utc",
            "valid_time_utc",
            "variable_name",
        ),
        timestamp_fields=("issue_time_utc", "valid_time_utc", "superseded_at_utc"),
        source_native_fields=("source_native_issue_time", "source_native_valid_time"),
    ),
    "raw_snapshots": DatasetQualityContract(
        dataset_name="raw_snapshots",
        table_name="raw_snapshots",
        required_fields=(
            "id",
            "source_name",
            "source_type",
            "retrieved_at_utc",
            "content_hash_sha256",
            "content_type",
            "parser_version",
            "storage_path",
            "byte_size",
            "ingestion_run_id",
        ),
        optional_fields=("retrieval_identifier", "source_url", "published_at_utc"),
        primary_key_fields=("source_name", "content_hash_sha256"),
        timestamp_fields=("retrieved_at_utc", "published_at_utc"),
        source_native_fields=("retrieval_identifier", "source_url"),
    ),
    "ingestion_runs": DatasetQualityContract(
        dataset_name="ingestion_runs",
        table_name="ingestion_runs",
        required_fields=(
            "id",
            "source_name",
            "source_type",
            "mode",
            "parser_version",
            "status",
            "started_at_utc",
            "records_seen",
            "records_loaded",
        ),
        optional_fields=("finished_at_utc", "error_type", "error_message"),
        primary_key_fields=("id",),
        timestamp_fields=("started_at_utc", "finished_at_utc"),
        source_native_fields=("source_name", "source_type", "parser_version"),
    ),
}


def get_dataset_contract(dataset_name: str) -> DatasetQualityContract:
    """Return the static quality contract for a supported M02 dataset."""

    try:
        return DATASET_CONTRACTS[dataset_name]
    except KeyError as exc:
        raise ValueError(f"unsupported quality dataset: {dataset_name}") from exc
