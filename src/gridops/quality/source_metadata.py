"""Deterministic quality checks for M02 source metadata tables."""

from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Protocol

from gridops.quality.checks import QualityCheckResult, failed_result, passed_result
from gridops.quality.contracts import QualityCheckCategory
from gridops.quality.results import MAX_SAFE_DETAIL_LENGTH

RAW_SNAPSHOTS_DATASET = "raw_snapshots"
INGESTION_RUNS_DATASET = "ingestion_runs"
VALID_INGESTION_STATUSES = {"running", "succeeded", "failed"}


class RawSnapshotQualityRecord(Protocol):
    """Attributes needed by raw snapshot metadata checks."""

    source_name: str | None
    source_type: str | None
    retrieved_at_utc: datetime
    content_hash_sha256: str | None
    content_type: str | None
    parser_version: str | None
    storage_path: str | None
    byte_size: int | None


class IngestionRunQualityRecord(Protocol):
    """Attributes needed by ingestion run metadata checks."""

    status: str | None
    started_at_utc: datetime
    finished_at_utc: datetime | None
    error_message: str | None
    records_seen: int | None
    records_loaded: int | None


def check_raw_snapshot_metadata(
    records: Iterable[RawSnapshotQualityRecord],
) -> QualityCheckResult:
    """Validate required raw snapshot retrieval and storage metadata."""

    failures = 0
    details: list[str] = []
    for record in records:
        row_errors = [
            field_name
            for field_name in (
                "source_name",
                "source_type",
                "content_hash_sha256",
                "content_type",
                "parser_version",
                "storage_path",
            )
            if getattr(record, field_name, None) in (None, "")
        ]
        if not _is_aware_utc(record.retrieved_at_utc):
            row_errors.append("retrieved_at_utc is not aware UTC")
        if record.byte_size is None or record.byte_size < 0:
            row_errors.append("byte_size is negative or missing")
        if row_errors:
            failures += 1
            details.extend(row_errors)

    if failures:
        return failed_result(
            dataset_name=RAW_SNAPSHOTS_DATASET,
            check_name="raw_snapshot_metadata",
            check_category=QualityCheckCategory.SOURCE_METADATA,
            observed_value=f"{failures} rows with invalid metadata",
            expected_value="required metadata populated with nonnegative byte_size",
            affected_record_count=failures,
            safe_detail="; ".join(sorted(set(details))),
        )

    return passed_result(
        dataset_name=RAW_SNAPSHOTS_DATASET,
        check_name="raw_snapshot_metadata",
        check_category=QualityCheckCategory.SOURCE_METADATA,
        observed_value="all raw snapshot metadata valid",
        expected_value="required metadata populated with nonnegative byte_size",
    )


def check_ingestion_run_metadata(
    records: Iterable[IngestionRunQualityRecord],
) -> QualityCheckResult:
    """Validate ingestion run lifecycle and safe failure metadata."""

    failures = 0
    details: list[str] = []
    for record in records:
        row_errors: list[str] = []
        if record.status not in VALID_INGESTION_STATUSES:
            row_errors.append("status is invalid")
        if not _is_aware_utc(record.started_at_utc):
            row_errors.append("started_at_utc is not aware UTC")
        if record.status in {"succeeded", "failed"} and record.finished_at_utc is None:
            row_errors.append("finished_at_utc is required for terminal runs")
        if record.finished_at_utc is not None and not _is_aware_utc(record.finished_at_utc):
            row_errors.append("finished_at_utc is not aware UTC")
        if record.records_seen is None or record.records_seen < 0:
            row_errors.append("records_seen is negative or missing")
        if record.records_loaded is None or record.records_loaded < 0:
            row_errors.append("records_loaded is negative or missing")
        if record.status == "failed" and record.error_message is not None:
            if len(record.error_message) > MAX_SAFE_DETAIL_LENGTH:
                row_errors.append("failed run error detail exceeds safe bound")
            if _contains_obvious_secret(record.error_message):
                row_errors.append("failed run error detail appears unsafe")
        if row_errors:
            failures += 1
            details.extend(row_errors)

    if failures:
        return failed_result(
            dataset_name=INGESTION_RUNS_DATASET,
            check_name="ingestion_run_metadata",
            check_category=QualityCheckCategory.SOURCE_METADATA,
            observed_value=f"{failures} rows with invalid metadata",
            expected_value="valid status, UTC timestamps, nonnegative counts, safe failure detail",
            affected_record_count=failures,
            safe_detail="; ".join(sorted(set(details))),
        )

    return passed_result(
        dataset_name=INGESTION_RUNS_DATASET,
        check_name="ingestion_run_metadata",
        check_category=QualityCheckCategory.SOURCE_METADATA,
        observed_value="all ingestion run metadata valid",
        expected_value="valid status, UTC timestamps, nonnegative counts, safe failure detail",
    )


def _is_aware_utc(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() == timedelta(0)


def _contains_obvious_secret(message: str) -> bool:
    lowered = message.lower()
    return any(
        marker in lowered
        for marker in (
            "password=",
            "passwd=",
            "secret=",
            "token=",
            "api_key=",
            "apikey=",
            "://user:",
        )
    )
