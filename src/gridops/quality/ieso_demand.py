"""Deterministic quality checks for IESO hourly demand records."""

from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Protocol

from gridops.quality.checks import QualityCheckResult, failed_result, passed_result, skipped_result
from gridops.quality.contracts import (
    QualityCheckCategory,
    QualitySeverity,
    get_dataset_contract,
)
from gridops.time_utils import TORONTO_TIME_ZONE, ieso_hour_ending_to_utc, utc_to_toronto

DATASET_NAME = "ieso_hourly_demand"
EXPECTED_INTERVAL_DURATION = timedelta(hours=1)
MIN_DEMAND_MW = Decimal("0")
# Conservative engineering guardrail for malformed fixtures, not an operational limit claim.
MAX_DEMAND_MW = Decimal("60000")
DEFAULT_FRESHNESS_TOLERANCE = timedelta(hours=30)


class IesoDemandQualityRecord(Protocol):
    """Attributes needed by IESO demand quality checks."""

    source_service_date: date
    source_hour_ending: int
    interval_start_utc: datetime
    interval_end_utc: datetime
    demand_mw: Decimal | None
    source_snapshot_id: int | None
    ingestion_run_id: int | None
    row_hash_sha256: str | None
    is_current: bool
    superseded_at_utc: datetime | None


def check_ieso_required_columns(available_columns: Iterable[str]) -> QualityCheckResult:
    """Validate that the IESO demand table exposes required contract fields."""

    contract = get_dataset_contract(DATASET_NAME)
    provided = set(available_columns)
    missing = sorted(set(contract.required_fields) - provided)

    if missing:
        return failed_result(
            dataset_name=DATASET_NAME,
            check_name="ieso_required_columns",
            check_category=QualityCheckCategory.SCHEMA,
            observed_value=", ".join(sorted(provided)),
            expected_value=", ".join(contract.required_fields),
            affected_record_count=len(missing),
            safe_detail=f"missing required columns: {', '.join(missing)}",
        )

    return passed_result(
        dataset_name=DATASET_NAME,
        check_name="ieso_required_columns",
        check_category=QualityCheckCategory.SCHEMA,
        observed_value=", ".join(sorted(provided)),
        expected_value=", ".join(contract.required_fields),
    )


def check_ieso_required_values(
    records: Iterable[IesoDemandQualityRecord],
) -> QualityCheckResult:
    """Validate nullability for required IESO demand fields."""

    contract = get_dataset_contract(DATASET_NAME)
    failed_fields: list[str] = []
    affected = 0

    for record in records:
        record_failed_fields = [
            field_name
            for field_name in contract.required_fields
            if getattr(record, field_name, None) is None
        ]
        if record_failed_fields:
            affected += 1
            failed_fields.extend(record_failed_fields)

    if affected:
        return failed_result(
            dataset_name=DATASET_NAME,
            check_name="ieso_required_values",
            check_category=QualityCheckCategory.SCHEMA,
            observed_value=f"{affected} rows with null required fields",
            expected_value="all required fields populated",
            affected_record_count=affected,
            safe_detail=f"null required fields: {', '.join(sorted(set(failed_fields)))}",
        )

    return passed_result(
        dataset_name=DATASET_NAME,
        check_name="ieso_required_values",
        check_category=QualityCheckCategory.SCHEMA,
        observed_value="all required fields populated",
        expected_value="all required fields populated",
    )


def check_ieso_unique_current_source_keys(
    records: Iterable[IesoDemandQualityRecord],
) -> QualityCheckResult:
    """Validate that current records have unique source-native keys."""

    seen: set[tuple[date, int]] = set()
    duplicates: set[tuple[date, int]] = set()

    for record in records:
        if not record.is_current:
            continue
        key = (record.source_service_date, record.source_hour_ending)
        if key in seen:
            duplicates.add(key)
        seen.add(key)

    if duplicates:
        detail = ", ".join(
            f"{service_date.isoformat()} HE{hour}" for service_date, hour in duplicates
        )
        return failed_result(
            dataset_name=DATASET_NAME,
            check_name="ieso_unique_current_source_keys",
            check_category=QualityCheckCategory.UNIQUENESS,
            observed_value=f"{len(duplicates)} duplicate current source keys",
            expected_value="0 duplicate current source keys",
            affected_record_count=len(duplicates),
            safe_detail=f"duplicate keys: {detail}",
        )

    return passed_result(
        dataset_name=DATASET_NAME,
        check_name="ieso_unique_current_source_keys",
        check_category=QualityCheckCategory.UNIQUENESS,
        observed_value="0 duplicate current source keys",
        expected_value="0 duplicate current source keys",
    )


def check_ieso_demand_range(
    records: Iterable[IesoDemandQualityRecord],
    *,
    minimum_mw: Decimal = MIN_DEMAND_MW,
    maximum_mw: Decimal = MAX_DEMAND_MW,
) -> QualityCheckResult:
    """Validate IESO demand values against conservative configured bounds."""

    failures = [
        record
        for record in records
        if record.demand_mw is None
        or record.demand_mw < minimum_mw
        or record.demand_mw > maximum_mw
    ]

    if failures:
        return failed_result(
            dataset_name=DATASET_NAME,
            check_name="ieso_demand_range",
            check_category=QualityCheckCategory.RANGE,
            observed_value=f"{len(failures)} rows outside range",
            expected_value=f"{minimum_mw} <= demand_mw <= {maximum_mw}",
            affected_record_count=len(failures),
            safe_detail="demand_mw outside conservative quality bounds",
        )

    return passed_result(
        dataset_name=DATASET_NAME,
        check_name="ieso_demand_range",
        check_category=QualityCheckCategory.RANGE,
        observed_value="all demand_mw values inside range",
        expected_value=f"{minimum_mw} <= demand_mw <= {maximum_mw}",
    )


def check_ieso_timestamps(records: Iterable[IesoDemandQualityRecord]) -> QualityCheckResult:
    """Validate UTC awareness, ordering, and one-hour interval duration."""

    failures = 0
    details: list[str] = []

    for record in records:
        row_errors: list[str] = []
        if not _is_aware_utc(record.interval_start_utc):
            row_errors.append("interval_start_utc is not aware UTC")
        if not _is_aware_utc(record.interval_end_utc):
            row_errors.append("interval_end_utc is not aware UTC")
        if row_errors:
            failures += 1
            details.extend(row_errors)
            continue
        if record.interval_start_utc >= record.interval_end_utc:
            row_errors.append("interval_start_utc is not before interval_end_utc")
        if record.interval_end_utc - record.interval_start_utc != EXPECTED_INTERVAL_DURATION:
            row_errors.append("interval duration is not one hour")
        if row_errors:
            failures += 1
            details.extend(row_errors)

    if failures:
        return failed_result(
            dataset_name=DATASET_NAME,
            check_name="ieso_timestamps",
            check_category=QualityCheckCategory.TIMESTAMP,
            observed_value=f"{failures} rows with invalid timestamps",
            expected_value="aware UTC one-hour intervals with start before end",
            affected_record_count=failures,
            safe_detail="; ".join(sorted(set(details))),
        )

    return passed_result(
        dataset_name=DATASET_NAME,
        check_name="ieso_timestamps",
        check_category=QualityCheckCategory.TIMESTAMP,
        observed_value="all timestamps valid",
        expected_value="aware UTC one-hour intervals with start before end",
    )


def check_ieso_continuity(
    records: Iterable[IesoDemandQualityRecord],
    *,
    window_start_utc: datetime,
    window_end_utc: datetime,
) -> QualityCheckResult:
    """Validate hourly UTC interval continuity inside a checked window."""

    window_start = _require_aware_utc(window_start_utc, "window_start_utc")
    window_end = _require_aware_utc(window_end_utc, "window_end_utc")
    if window_start >= window_end:
        raise ValueError("checked window start must be before checked window end")

    expected_starts = set(_hourly_starts(window_start, window_end))
    observed_starts = {
        record.interval_start_utc
        for record in records
        if record.is_current
        and _is_aware_utc(record.interval_start_utc)
        and window_start <= record.interval_start_utc < window_end
    }
    missing = sorted(expected_starts - observed_starts)

    if missing:
        return failed_result(
            dataset_name=DATASET_NAME,
            check_name="ieso_utc_interval_continuity",
            check_category=QualityCheckCategory.CONTINUITY,
            observed_value=f"{len(observed_starts)} of {len(expected_starts)} expected intervals",
            expected_value=f"{len(expected_starts)} hourly intervals",
            affected_record_count=len(missing),
            safe_detail=f"missing interval starts: {_format_datetimes(missing)}",
        )

    return passed_result(
        dataset_name=DATASET_NAME,
        check_name="ieso_utc_interval_continuity",
        check_category=QualityCheckCategory.CONTINUITY,
        observed_value=f"{len(observed_starts)} expected intervals present",
        expected_value=f"{len(expected_starts)} hourly intervals",
    )


def check_ieso_source_hour_completeness(
    records: Iterable[IesoDemandQualityRecord],
    *,
    window_start_utc: datetime,
    window_end_utc: datetime,
) -> QualityCheckResult:
    """Validate expected source-native hour-ending keys inside a UTC window."""

    window_start = _require_aware_utc(window_start_utc, "window_start_utc")
    window_end = _require_aware_utc(window_end_utc, "window_end_utc")
    if window_start >= window_end:
        raise ValueError("checked window start must be before checked window end")

    expected_keys = {
        _source_key_for_interval_start(start) for start in _hourly_starts(window_start, window_end)
    }
    observed_keys = {
        (record.source_service_date, record.source_hour_ending)
        for record in records
        if record.is_current and window_start <= record.interval_start_utc < window_end
    }
    missing = sorted(expected_keys - observed_keys)

    if missing:
        return failed_result(
            dataset_name=DATASET_NAME,
            check_name="ieso_source_hour_completeness",
            check_category=QualityCheckCategory.COMPLETENESS,
            observed_value=f"{len(observed_keys)} of {len(expected_keys)} expected source-hour keys",
            expected_value=f"{len(expected_keys)} source-hour keys",
            affected_record_count=len(missing),
            safe_detail=f"missing source-hour keys: {_format_source_keys(missing)}",
        )

    return passed_result(
        dataset_name=DATASET_NAME,
        check_name="ieso_source_hour_completeness",
        check_category=QualityCheckCategory.COMPLETENESS,
        observed_value=f"{len(observed_keys)} expected source-hour keys present",
        expected_value=f"{len(expected_keys)} source-hour keys",
    )


def check_ieso_freshness(
    records: Iterable[IesoDemandQualityRecord],
    *,
    now_utc: datetime,
    tolerance: timedelta = DEFAULT_FRESHNESS_TOLERANCE,
) -> QualityCheckResult:
    """Validate latest current IESO interval is recent enough using a fixed clock."""

    now = _require_aware_utc(now_utc, "now_utc")
    latest = max(
        (
            record.interval_end_utc
            for record in records
            if record.is_current and _is_aware_utc(record.interval_end_utc)
        ),
        default=None,
    )

    if latest is None:
        return failed_result(
            dataset_name=DATASET_NAME,
            check_name="ieso_freshness",
            check_category=QualityCheckCategory.FRESHNESS,
            severity=QualitySeverity.CRITICAL,
            observed_value="no current intervals",
            expected_value=f"latest interval within {tolerance}",
            affected_record_count=0,
            safe_detail="no current IESO demand records available",
        )

    age = now - latest
    if age > tolerance:
        return failed_result(
            dataset_name=DATASET_NAME,
            check_name="ieso_freshness",
            check_category=QualityCheckCategory.FRESHNESS,
            severity=QualitySeverity.ERROR,
            observed_value=str(age),
            expected_value=f"<= {tolerance}",
            affected_record_count=1,
            safe_detail=f"latest interval_end_utc is {latest.isoformat()}",
        )

    return passed_result(
        dataset_name=DATASET_NAME,
        check_name="ieso_freshness",
        check_category=QualityCheckCategory.FRESHNESS,
        observed_value=str(age),
        expected_value=f"<= {tolerance}",
    )


def check_ieso_dst_alignment(
    records: Iterable[IesoDemandQualityRecord],
    *,
    window_start_utc: datetime,
    window_end_utc: datetime,
) -> QualityCheckResult:
    """Validate source-native hour-ending alignment with M01 time utilities."""

    window_start = _require_aware_utc(window_start_utc, "window_start_utc")
    window_end = _require_aware_utc(window_end_utc, "window_end_utc")
    if window_start >= window_end:
        raise ValueError("checked window start must be before checked window end")

    if _window_contains_fall_back_ambiguous_endpoint(window_start, window_end):
        return skipped_result(
            dataset_name=DATASET_NAME,
            check_name="ieso_dst_alignment",
            check_category=QualityCheckCategory.DST,
            observed_value="fall-back ambiguous endpoint in checked window",
            expected_value="unambiguous IESO source-native hour-ending keys",
            safe_detail=(
                "Current M02 source_service_date + source_hour_ending keys cannot distinguish "
                "the repeated fall-back operating hour without additional source-native detail."
            ),
        )

    failures = 0
    details: list[str] = []
    for record in records:
        if not record.is_current or not (window_start <= record.interval_start_utc < window_end):
            continue
        try:
            service_midnight = datetime(
                record.source_service_date.year,
                record.source_service_date.month,
                record.source_service_date.day,
                tzinfo=TORONTO_TIME_ZONE,
            )
            expected_end = ieso_hour_ending_to_utc(
                service_midnight,
                record.source_hour_ending,
            )
        except ValueError as exc:
            failures += 1
            details.append(str(exc))
            continue
        if expected_end != record.interval_end_utc:
            failures += 1
            details.append("source-native hour-ending does not match interval_end_utc")

    if failures:
        return failed_result(
            dataset_name=DATASET_NAME,
            check_name="ieso_dst_alignment",
            check_category=QualityCheckCategory.DST,
            observed_value=f"{failures} rows failed DST alignment",
            expected_value="source-native hour-ending maps to interval_end_utc",
            affected_record_count=failures,
            safe_detail="; ".join(sorted(set(details))),
        )

    return passed_result(
        dataset_name=DATASET_NAME,
        check_name="ieso_dst_alignment",
        check_category=QualityCheckCategory.DST,
        observed_value="all checked rows align with M01 time utilities",
        expected_value="source-native hour-ending maps to interval_end_utc",
    )


def _is_aware_utc(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() == timedelta(0)


def _require_aware_utc(value: datetime, name: str) -> datetime:
    if not _is_aware_utc(value):
        raise ValueError(f"{name} must be timezone-aware UTC")

    return value.astimezone(UTC)


def _hourly_starts(window_start_utc: datetime, window_end_utc: datetime) -> list[datetime]:
    starts: list[datetime] = []
    cursor = window_start_utc
    while cursor < window_end_utc:
        starts.append(cursor)
        cursor += EXPECTED_INTERVAL_DURATION

    return starts


def _source_key_for_interval_start(interval_start_utc: datetime) -> tuple[date, int]:
    interval_end_local = utc_to_toronto(interval_start_utc + EXPECTED_INTERVAL_DURATION)
    if interval_end_local.hour == 0:
        return (interval_end_local.date() - timedelta(days=1), 24)

    return (interval_end_local.date(), interval_end_local.hour)


def _window_contains_fall_back_ambiguous_endpoint(
    window_start_utc: datetime,
    window_end_utc: datetime,
) -> bool:
    for interval_start in _hourly_starts(window_start_utc, window_end_utc):
        local_end = utc_to_toronto(interval_start + EXPECTED_INTERVAL_DURATION)
        if local_end.fold == 1 and local_end.hour == 1:
            return True

    return False


def _format_datetimes(values: list[datetime]) -> str:
    return ", ".join(value.isoformat() for value in values[:5])


def _format_source_keys(values: list[tuple[date, int]]) -> str:
    return ", ".join(f"{service_date.isoformat()} HE{hour}" for service_date, hour in values[:5])
