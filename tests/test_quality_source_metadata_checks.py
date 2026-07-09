"""Tests for source metadata quality checks."""

from dataclasses import dataclass
from datetime import UTC, datetime

from gridops.quality.contracts import QualityResultStatus
from gridops.quality.source_metadata import (
    check_ingestion_run_metadata,
    check_raw_snapshot_metadata,
)


@dataclass(slots=True)
class RawSnapshotRecord:
    source_name: str | None = "ieso-hourly-demand"
    source_type: str | None = "electricity_demand"
    retrieved_at_utc: datetime = datetime(2026, 7, 9, 12, tzinfo=UTC)
    content_hash_sha256: str | None = "a" * 64
    content_type: str | None = "text/csv"
    parser_version: str | None = "ieso-hourly-demand:v1"
    storage_path: str | None = "ieso-hourly-demand/a.csv"
    byte_size: int | None = 100


@dataclass(slots=True)
class IngestionRunRecord:
    status: str | None = "succeeded"
    started_at_utc: datetime = datetime(2026, 7, 9, 12, tzinfo=UTC)
    finished_at_utc: datetime | None = datetime(2026, 7, 9, 12, 1, tzinfo=UTC)
    error_message: str | None = None
    records_seen: int | None = 3
    records_loaded: int | None = 3


def test_raw_snapshot_metadata_check_passes() -> None:
    result = check_raw_snapshot_metadata([RawSnapshotRecord()])

    assert result.status == QualityResultStatus.PASSED


def test_raw_snapshot_metadata_check_fails() -> None:
    result = check_raw_snapshot_metadata(
        [
            RawSnapshotRecord(
                source_name=None,
                retrieved_at_utc=datetime(2026, 7, 9, 12),
                byte_size=-1,
            )
        ]
    )

    assert result.status == QualityResultStatus.FAILED
    assert result.safe_detail is not None
    assert "source_name" in result.safe_detail
    assert "byte_size" in result.safe_detail


def test_ingestion_run_metadata_check_passes() -> None:
    result = check_ingestion_run_metadata(
        [
            IngestionRunRecord(),
            IngestionRunRecord(
                status="failed",
                error_message="connection failed [REDACTED]",
            ),
        ]
    )

    assert result.status == QualityResultStatus.PASSED


def test_ingestion_run_metadata_check_fails() -> None:
    result = check_ingestion_run_metadata(
        [
            IngestionRunRecord(
                status="failed",
                finished_at_utc=None,
                error_message="password=secret",
                records_seen=-1,
            )
        ]
    )

    assert result.status == QualityResultStatus.FAILED
    assert result.safe_detail is not None
    assert "finished_at_utc" in result.safe_detail
    assert "records_seen" in result.safe_detail
    assert "unsafe" in result.safe_detail
