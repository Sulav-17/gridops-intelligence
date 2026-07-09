"""Tests for IESO hourly demand quality checks."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from gridops.quality.contracts import QualityCheckCategory, QualityResultStatus, QualitySeverity
from gridops.quality.ieso_demand import (
    check_ieso_continuity,
    check_ieso_demand_range,
    check_ieso_dst_alignment,
    check_ieso_freshness,
    check_ieso_required_columns,
    check_ieso_required_values,
    check_ieso_source_hour_completeness,
    check_ieso_timestamps,
    check_ieso_unique_current_source_keys,
)
from gridops.time_utils import TORONTO_TIME_ZONE, ieso_hour_ending_to_utc


@dataclass(slots=True)
class IesoDemandRecord:
    """Minimal IESO demand quality record for deterministic tests."""

    source_service_date: date
    source_hour_ending: int
    interval_start_utc: datetime
    interval_end_utc: datetime
    demand_mw: Decimal | None = Decimal("18000")
    source_snapshot_id: int | None = 1
    ingestion_run_id: int | None = 1
    row_hash_sha256: str | None = "a" * 64
    is_current: bool = True
    superseded_at_utc: datetime | None = None
    id: int | None = 1


def test_ieso_schema_check_passes_with_required_columns() -> None:
    result = check_ieso_required_columns(
        {
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
            "superseded_at_utc",
        }
    )

    assert result.status == QualityResultStatus.PASSED
    assert result.check_category == QualityCheckCategory.SCHEMA


def test_ieso_schema_check_fails_with_missing_required_column() -> None:
    result = check_ieso_required_columns({"source_service_date", "source_hour_ending"})

    assert result.status == QualityResultStatus.FAILED
    assert result.affected_record_count == 8
    assert result.safe_detail is not None
    assert "interval_start_utc" in result.safe_detail


def test_ieso_nullability_check_passes_when_required_values_present() -> None:
    result = check_ieso_required_values([_record(1)])

    assert result.status == QualityResultStatus.PASSED


def test_ieso_nullability_check_fails_when_required_value_is_none() -> None:
    record = _record(1)
    record.row_hash_sha256 = None

    result = check_ieso_required_values([record])

    assert result.status == QualityResultStatus.FAILED
    assert result.affected_record_count == 1
    assert result.safe_detail is not None
    assert "row_hash_sha256" in result.safe_detail


def test_ieso_uniqueness_check_passes_for_unique_current_source_keys() -> None:
    result = check_ieso_unique_current_source_keys([_record(1), _record(2)])

    assert result.status == QualityResultStatus.PASSED


def test_ieso_uniqueness_check_fails_for_duplicate_current_source_keys() -> None:
    duplicate = _record(1)
    duplicate.id = 2

    result = check_ieso_unique_current_source_keys([_record(1), duplicate])

    assert result.status == QualityResultStatus.FAILED
    assert result.affected_record_count == 1
    assert result.is_blocking is True


def test_ieso_demand_range_check_passes_for_conservative_bounds() -> None:
    result = check_ieso_demand_range([_record(1, demand_mw=Decimal("18000"))])

    assert result.status == QualityResultStatus.PASSED


def test_ieso_demand_range_check_fails_outside_conservative_bounds() -> None:
    result = check_ieso_demand_range([_record(1, demand_mw=Decimal("70000"))])

    assert result.status == QualityResultStatus.FAILED
    assert result.affected_record_count == 1


def test_ieso_timestamp_check_passes_for_aware_one_hour_utc_interval() -> None:
    result = check_ieso_timestamps([_record(1)])

    assert result.status == QualityResultStatus.PASSED


def test_ieso_timestamp_check_fails_for_wrong_duration() -> None:
    record = _record(1)
    record.interval_end_utc = record.interval_start_utc + timedelta(hours=2)

    result = check_ieso_timestamps([record])

    assert result.status == QualityResultStatus.FAILED
    assert result.safe_detail is not None
    assert "duration" in result.safe_detail


def test_ieso_continuity_check_passes_for_hourly_utc_window() -> None:
    records = [_record(1), _record(2), _record(3)]

    result = check_ieso_continuity(
        records,
        window_start_utc=datetime(2026, 1, 15, 5, tzinfo=UTC),
        window_end_utc=datetime(2026, 1, 15, 8, tzinfo=UTC),
    )

    assert result.status == QualityResultStatus.PASSED


def test_ieso_continuity_check_fails_for_missing_hourly_interval() -> None:
    records = [_record(1), _record(3)]

    result = check_ieso_continuity(
        records,
        window_start_utc=datetime(2026, 1, 15, 5, tzinfo=UTC),
        window_end_utc=datetime(2026, 1, 15, 8, tzinfo=UTC),
    )

    assert result.status == QualityResultStatus.FAILED
    assert result.affected_record_count == 1
    assert result.safe_detail is not None
    assert "2026-01-15T06:00:00+00:00" in result.safe_detail


def test_ieso_completeness_check_passes_for_expected_source_hours() -> None:
    records = [_record(1), _record(2), _record(3)]

    result = check_ieso_source_hour_completeness(
        records,
        window_start_utc=datetime(2026, 1, 15, 5, tzinfo=UTC),
        window_end_utc=datetime(2026, 1, 15, 8, tzinfo=UTC),
    )

    assert result.status == QualityResultStatus.PASSED


def test_ieso_completeness_check_fails_for_missing_source_hour() -> None:
    records = [_record(1), _record(3)]

    result = check_ieso_source_hour_completeness(
        records,
        window_start_utc=datetime(2026, 1, 15, 5, tzinfo=UTC),
        window_end_utc=datetime(2026, 1, 15, 8, tzinfo=UTC),
    )

    assert result.status == QualityResultStatus.FAILED
    assert result.affected_record_count == 1
    assert result.safe_detail is not None
    assert "HE2" in result.safe_detail


def test_ieso_freshness_check_passes_with_fixed_clock() -> None:
    result = check_ieso_freshness(
        [_record(24)],
        now_utc=datetime(2026, 1, 16, 6, tzinfo=UTC),
        tolerance=timedelta(hours=2),
    )

    assert result.status == QualityResultStatus.PASSED


def test_ieso_freshness_check_fails_with_fixed_clock() -> None:
    result = check_ieso_freshness(
        [_record(24)],
        now_utc=datetime(2026, 1, 17, 12, tzinfo=UTC),
        tolerance=timedelta(hours=2),
    )

    assert result.status == QualityResultStatus.FAILED
    assert result.severity == QualitySeverity.ERROR


def test_ieso_dst_alignment_passes_for_spring_forward_representable_hours() -> None:
    service_date = date(2026, 3, 8)
    records = [_record_for_service_hour(service_date, hour) for hour in range(3, 25)]

    result = check_ieso_dst_alignment(
        records,
        window_start_utc=datetime(2026, 3, 8, 7, tzinfo=UTC),
        window_end_utc=datetime(2026, 3, 9, 4, tzinfo=UTC),
    )

    assert result.status == QualityResultStatus.PASSED


def test_ieso_dst_alignment_skips_fall_back_ambiguous_window_honestly() -> None:
    result = check_ieso_dst_alignment(
        [],
        window_start_utc=datetime(2026, 11, 1, 4, tzinfo=UTC),
        window_end_utc=datetime(2026, 11, 1, 8, tzinfo=UTC),
    )

    assert result.status == QualityResultStatus.SKIPPED
    assert result.severity == QualitySeverity.WARNING
    assert result.safe_detail is not None
    assert "cannot distinguish" in result.safe_detail


def _record(hour_ending: int, *, demand_mw: Decimal = Decimal("18000")) -> IesoDemandRecord:
    return _record_for_service_hour(date(2026, 1, 15), hour_ending, demand_mw=demand_mw)


def _record_for_service_hour(
    service_date: date,
    hour_ending: int,
    *,
    demand_mw: Decimal = Decimal("18000"),
) -> IesoDemandRecord:
    service_midnight = datetime(
        service_date.year,
        service_date.month,
        service_date.day,
        tzinfo=TORONTO_TIME_ZONE,
    )
    interval_end = ieso_hour_ending_to_utc(service_midnight, hour_ending)
    return IesoDemandRecord(
        source_service_date=service_date,
        source_hour_ending=hour_ending,
        interval_start_utc=interval_end - timedelta(hours=1),
        interval_end_utc=interval_end,
        demand_mw=demand_mw,
    )
