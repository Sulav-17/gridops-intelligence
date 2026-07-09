"""Deterministic quality checks for M02 weather datasets."""

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol

from gridops.quality.checks import QualityCheckResult, failed_result, passed_result, skipped_result
from gridops.quality.contracts import QualityCheckCategory, QualitySeverity, get_dataset_contract

OBSERVATIONS_DATASET = "weather_observations"
FORECASTS_DATASET = "weather_forecasts"
DEFAULT_OBSERVATION_FRESHNESS_TOLERANCE = timedelta(hours=6)
DEFAULT_FORECAST_FRESHNESS_TOLERANCE = timedelta(hours=24)
MIN_TEMPERATURE_C = Decimal("-80")
MAX_TEMPERATURE_C = Decimal("60")
MIN_FORECAST_VALUE = Decimal("-1000")
MAX_FORECAST_VALUE = Decimal("1000")


class WeatherObservationQualityRecord(Protocol):
    """Attributes needed by weather observation quality checks."""

    source_name: str | None
    source_station_id: str | None
    source_native_timestamp: str | None
    observed_at_utc: datetime
    temperature_c: Decimal | None
    relative_humidity_percent: Decimal | None
    wind_speed_kph: Decimal | None
    precipitation_mm: Decimal | None
    source_snapshot_id: int | None
    ingestion_run_id: int | None
    row_hash_sha256: str | None
    is_current: bool
    superseded_at_utc: datetime | None


class WeatherForecastQualityRecord(Protocol):
    """Attributes needed by weather forecast quality checks."""

    source_name: str | None
    forecast_location: str | None
    source_native_issue_time: str | None
    source_native_valid_time: str | None
    issue_time_utc: datetime
    valid_time_utc: datetime
    lead_time_hours: int | None
    variable_name: str | None
    variable_value: Decimal | None
    variable_unit: str | None
    source_snapshot_id: int | None
    ingestion_run_id: int | None
    row_hash_sha256: str | None
    is_current: bool
    superseded_at_utc: datetime | None


def check_weather_observation_required_columns(
    available_columns: Iterable[str],
) -> QualityCheckResult:
    """Validate required weather observation columns."""

    return _check_required_columns(
        dataset_name=OBSERVATIONS_DATASET,
        check_name="weather_observation_required_columns",
        available_columns=available_columns,
    )


def check_weather_forecast_required_columns(available_columns: Iterable[str]) -> QualityCheckResult:
    """Validate required weather forecast columns."""

    return _check_required_columns(
        dataset_name=FORECASTS_DATASET,
        check_name="weather_forecast_required_columns",
        available_columns=available_columns,
    )


def check_weather_observation_required_values(
    records: Iterable[WeatherObservationQualityRecord],
) -> QualityCheckResult:
    """Validate nullability for required weather observation fields."""

    return _check_required_values(
        dataset_name=OBSERVATIONS_DATASET,
        check_name="weather_observation_required_values",
        records=records,
    )


def check_weather_forecast_required_values(
    records: Iterable[WeatherForecastQualityRecord],
) -> QualityCheckResult:
    """Validate nullability for required weather forecast fields."""

    return _check_required_values(
        dataset_name=FORECASTS_DATASET,
        check_name="weather_forecast_required_values",
        records=records,
    )


def check_weather_observation_unique_current_source_keys(
    records: Iterable[WeatherObservationQualityRecord],
) -> QualityCheckResult:
    """Validate current weather observations are unique by source, station, and timestamp."""

    seen: set[tuple[str | None, str | None, datetime]] = set()
    duplicates: set[tuple[str | None, str | None, datetime]] = set()
    for record in records:
        if not record.is_current:
            continue
        key = (record.source_name, record.source_station_id, record.observed_at_utc)
        if key in seen:
            duplicates.add(key)
        seen.add(key)

    if duplicates:
        return failed_result(
            dataset_name=OBSERVATIONS_DATASET,
            check_name="weather_observation_unique_current_source_keys",
            check_category=QualityCheckCategory.UNIQUENESS,
            observed_value=f"{len(duplicates)} duplicate current source keys",
            expected_value="0 duplicate current source keys",
            affected_record_count=len(duplicates),
            safe_detail="duplicate observation keys detected",
        )

    return passed_result(
        dataset_name=OBSERVATIONS_DATASET,
        check_name="weather_observation_unique_current_source_keys",
        check_category=QualityCheckCategory.UNIQUENESS,
        observed_value="0 duplicate current source keys",
        expected_value="0 duplicate current source keys",
    )


def check_weather_forecast_unique_current_source_keys(
    records: Iterable[WeatherForecastQualityRecord],
) -> QualityCheckResult:
    """Validate current weather forecasts are unique by source forecast key."""

    seen: set[tuple[str | None, str | None, datetime, datetime, str | None]] = set()
    duplicates: set[tuple[str | None, str | None, datetime, datetime, str | None]] = set()
    for record in records:
        if not record.is_current:
            continue
        key = (
            record.source_name,
            record.forecast_location,
            record.issue_time_utc,
            record.valid_time_utc,
            record.variable_name,
        )
        if key in seen:
            duplicates.add(key)
        seen.add(key)

    if duplicates:
        return failed_result(
            dataset_name=FORECASTS_DATASET,
            check_name="weather_forecast_unique_current_source_keys",
            check_category=QualityCheckCategory.UNIQUENESS,
            observed_value=f"{len(duplicates)} duplicate current forecast keys",
            expected_value="0 duplicate current forecast keys",
            affected_record_count=len(duplicates),
            safe_detail="duplicate forecast keys detected",
        )

    return passed_result(
        dataset_name=FORECASTS_DATASET,
        check_name="weather_forecast_unique_current_source_keys",
        check_category=QualityCheckCategory.UNIQUENESS,
        observed_value="0 duplicate current forecast keys",
        expected_value="0 duplicate current forecast keys",
    )


def check_weather_observation_ranges(
    records: Iterable[WeatherObservationQualityRecord],
) -> QualityCheckResult:
    """Validate weather observation values against conservative ranges."""

    failures = 0
    details: list[str] = []
    for record in records:
        row_errors: list[str] = []
        if record.temperature_c is not None and not (
            MIN_TEMPERATURE_C <= record.temperature_c <= MAX_TEMPERATURE_C
        ):
            row_errors.append("temperature_c outside conservative range")
        if record.relative_humidity_percent is not None and not (
            Decimal("0") <= record.relative_humidity_percent <= Decimal("100")
        ):
            row_errors.append("relative_humidity_percent outside 0..100")
        if record.wind_speed_kph is not None and record.wind_speed_kph < 0:
            row_errors.append("wind_speed_kph is negative")
        if record.precipitation_mm is not None and record.precipitation_mm < 0:
            row_errors.append("precipitation_mm is negative")
        if row_errors:
            failures += 1
            details.extend(row_errors)

    if failures:
        return failed_result(
            dataset_name=OBSERVATIONS_DATASET,
            check_name="weather_observation_ranges",
            check_category=QualityCheckCategory.RANGE,
            observed_value=f"{failures} rows outside range",
            expected_value="temperature -80..60 C; humidity 0..100; wind/precipitation nonnegative",
            affected_record_count=failures,
            safe_detail="; ".join(sorted(set(details))),
        )

    return passed_result(
        dataset_name=OBSERVATIONS_DATASET,
        check_name="weather_observation_ranges",
        check_category=QualityCheckCategory.RANGE,
        observed_value="all present weather observation values inside range",
        expected_value="temperature -80..60 C; humidity 0..100; wind/precipitation nonnegative",
    )


def check_weather_forecast_ranges(
    records: Iterable[WeatherForecastQualityRecord],
    *,
    minimum_value: Decimal = MIN_FORECAST_VALUE,
    maximum_value: Decimal = MAX_FORECAST_VALUE,
) -> QualityCheckResult:
    """Validate forecast values against broad provider-neutral bounds."""

    failures = [
        record
        for record in records
        if record.variable_value is None
        or record.variable_value < minimum_value
        or record.variable_value > maximum_value
    ]
    if failures:
        return failed_result(
            dataset_name=FORECASTS_DATASET,
            check_name="weather_forecast_ranges",
            check_category=QualityCheckCategory.RANGE,
            observed_value=f"{len(failures)} rows outside range",
            expected_value=f"{minimum_value} <= variable_value <= {maximum_value}",
            affected_record_count=len(failures),
            safe_detail="variable_value outside broad provider-neutral quality bounds",
        )

    return passed_result(
        dataset_name=FORECASTS_DATASET,
        check_name="weather_forecast_ranges",
        check_category=QualityCheckCategory.RANGE,
        observed_value="all forecast values inside range",
        expected_value=f"{minimum_value} <= variable_value <= {maximum_value}",
    )


def check_weather_observation_timestamps(
    records: Iterable[WeatherObservationQualityRecord],
) -> QualityCheckResult:
    """Validate weather observation timestamps are aware UTC."""

    failures = sum(1 for record in records if not _is_aware_utc(record.observed_at_utc))
    if failures:
        return failed_result(
            dataset_name=OBSERVATIONS_DATASET,
            check_name="weather_observation_timestamps",
            check_category=QualityCheckCategory.TIMESTAMP,
            observed_value=f"{failures} rows with invalid timestamps",
            expected_value="observed_at_utc is timezone-aware UTC",
            affected_record_count=failures,
            safe_detail="observed_at_utc must be timezone-aware UTC",
        )

    return passed_result(
        dataset_name=OBSERVATIONS_DATASET,
        check_name="weather_observation_timestamps",
        check_category=QualityCheckCategory.TIMESTAMP,
        observed_value="all observation timestamps are aware UTC",
        expected_value="observed_at_utc is timezone-aware UTC",
    )


def check_weather_forecast_timestamps(
    records: Iterable[WeatherForecastQualityRecord],
) -> QualityCheckResult:
    """Validate forecast issue/valid timestamps and optional lead hours."""

    failures = 0
    details: list[str] = []
    for record in records:
        row_errors: list[str] = []
        if not _is_aware_utc(record.issue_time_utc):
            row_errors.append("issue_time_utc is not aware UTC")
        if not _is_aware_utc(record.valid_time_utc):
            row_errors.append("valid_time_utc is not aware UTC")
        if row_errors:
            failures += 1
            details.extend(row_errors)
            continue
        delta = record.valid_time_utc - record.issue_time_utc
        if delta <= timedelta(0):
            row_errors.append("valid_time_utc is not after issue_time_utc")
        if record.lead_time_hours is not None:
            expected_lead = _whole_hours(delta)
            if expected_lead is None or record.lead_time_hours != expected_lead:
                row_errors.append("lead_time_hours does not match issue-to-valid whole hours")
        if row_errors:
            failures += 1
            details.extend(row_errors)

    if failures:
        return failed_result(
            dataset_name=FORECASTS_DATASET,
            check_name="weather_forecast_timestamps",
            check_category=QualityCheckCategory.TIMESTAMP,
            observed_value=f"{failures} rows with invalid timestamps",
            expected_value="aware UTC issue/valid timestamps with matching lead hours",
            affected_record_count=failures,
            safe_detail="; ".join(sorted(set(details))),
        )

    return passed_result(
        dataset_name=FORECASTS_DATASET,
        check_name="weather_forecast_timestamps",
        check_category=QualityCheckCategory.TIMESTAMP,
        observed_value="all forecast timestamps valid",
        expected_value="aware UTC issue/valid timestamps with matching lead hours",
    )


def check_weather_observation_continuity(
    records: Iterable[WeatherObservationQualityRecord],
    *,
    station_id: str,
    window_start_utc: datetime,
    window_end_utc: datetime,
    expected_interval: timedelta = timedelta(hours=1),
) -> QualityCheckResult:
    """Validate fixture-supported hourly observation coverage for one station."""

    window_start = _require_aware_utc(window_start_utc, "window_start_utc")
    window_end = _require_aware_utc(window_end_utc, "window_end_utc")
    if window_start >= window_end:
        raise ValueError("checked window start must be before checked window end")
    if expected_interval != timedelta(hours=1):
        return skipped_result(
            dataset_name=OBSERVATIONS_DATASET,
            check_name="weather_observation_continuity",
            check_category=QualityCheckCategory.CONTINUITY,
            observed_value=str(expected_interval),
            expected_value="hourly fixture assumption",
            safe_detail="weather observation continuity is only defined for hourly fixture windows",
        )

    expected = set(_expected_times(window_start, window_end, expected_interval))
    observed = {
        record.observed_at_utc
        for record in records
        if record.is_current
        and record.source_station_id == station_id
        and _is_aware_utc(record.observed_at_utc)
        and window_start <= record.observed_at_utc < window_end
    }
    missing = sorted(expected - observed)
    if missing:
        return failed_result(
            dataset_name=OBSERVATIONS_DATASET,
            check_name="weather_observation_continuity",
            check_category=QualityCheckCategory.CONTINUITY,
            observed_value=f"{len(observed)} of {len(expected)} expected observations",
            expected_value=f"{len(expected)} hourly observations",
            affected_record_count=len(missing),
            safe_detail=f"missing observation timestamps: {_format_datetimes(missing)}",
        )

    return passed_result(
        dataset_name=OBSERVATIONS_DATASET,
        check_name="weather_observation_continuity",
        check_category=QualityCheckCategory.CONTINUITY,
        observed_value=f"{len(observed)} expected observations present",
        expected_value=f"{len(expected)} hourly observations",
    )


def check_weather_forecast_valid_time_completeness(
    records: Iterable[WeatherForecastQualityRecord],
    *,
    forecast_location: str,
    variable_name: str,
    issue_time_utc: datetime,
    expected_valid_times_utc: Iterable[datetime],
) -> QualityCheckResult:
    """Validate fixture-supported valid-time completeness for one forecast issue."""

    issue_time = _require_aware_utc(issue_time_utc, "issue_time_utc")
    expected = {
        _require_aware_utc(value, "expected_valid_time") for value in expected_valid_times_utc
    }
    if not expected:
        return skipped_result(
            dataset_name=FORECASTS_DATASET,
            check_name="weather_forecast_valid_time_completeness",
            check_category=QualityCheckCategory.COMPLETENESS,
            observed_value="no expected valid times supplied",
            expected_value="caller-provided fixture valid times",
            safe_detail="forecast completeness requires caller-provided expected valid times",
        )

    observed = {
        record.valid_time_utc
        for record in records
        if record.is_current
        and record.forecast_location == forecast_location
        and record.variable_name == variable_name
        and record.issue_time_utc == issue_time
        and _is_aware_utc(record.valid_time_utc)
    }
    missing = sorted(expected - observed)
    if missing:
        return failed_result(
            dataset_name=FORECASTS_DATASET,
            check_name="weather_forecast_valid_time_completeness",
            check_category=QualityCheckCategory.COMPLETENESS,
            observed_value=f"{len(observed)} of {len(expected)} expected valid times",
            expected_value=f"{len(expected)} caller-provided valid times",
            affected_record_count=len(missing),
            safe_detail=f"missing valid times: {_format_datetimes(missing)}",
        )

    return passed_result(
        dataset_name=FORECASTS_DATASET,
        check_name="weather_forecast_valid_time_completeness",
        check_category=QualityCheckCategory.COMPLETENESS,
        observed_value=f"{len(observed)} expected valid times present",
        expected_value=f"{len(expected)} caller-provided valid times",
    )


def check_weather_observation_freshness(
    records: Iterable[WeatherObservationQualityRecord],
    *,
    now_utc: datetime,
    tolerance: timedelta = DEFAULT_OBSERVATION_FRESHNESS_TOLERANCE,
) -> QualityCheckResult:
    """Validate latest current weather observation using a fixed clock."""

    return _check_freshness(
        dataset_name=OBSERVATIONS_DATASET,
        check_name="weather_observation_freshness",
        timestamps=(
            record.observed_at_utc
            for record in records
            if record.is_current and _is_aware_utc(record.observed_at_utc)
        ),
        now_utc=now_utc,
        tolerance=tolerance,
    )


def check_weather_forecast_freshness(
    records: Iterable[WeatherForecastQualityRecord],
    *,
    now_utc: datetime,
    tolerance: timedelta = DEFAULT_FORECAST_FRESHNESS_TOLERANCE,
) -> QualityCheckResult:
    """Validate latest current forecast issue time using a fixed clock."""

    return _check_freshness(
        dataset_name=FORECASTS_DATASET,
        check_name="weather_forecast_freshness",
        timestamps=(
            record.issue_time_utc
            for record in records
            if record.is_current and _is_aware_utc(record.issue_time_utc)
        ),
        now_utc=now_utc,
        tolerance=tolerance,
    )


def _check_required_columns(
    *,
    dataset_name: str,
    check_name: str,
    available_columns: Iterable[str],
) -> QualityCheckResult:
    contract = get_dataset_contract(dataset_name)
    provided = set(available_columns)
    missing = sorted(set(contract.required_fields) - provided)
    if missing:
        return failed_result(
            dataset_name=dataset_name,
            check_name=check_name,
            check_category=QualityCheckCategory.SCHEMA,
            observed_value=", ".join(sorted(provided)),
            expected_value=", ".join(contract.required_fields),
            affected_record_count=len(missing),
            safe_detail=f"missing required columns: {', '.join(missing)}",
        )

    return passed_result(
        dataset_name=dataset_name,
        check_name=check_name,
        check_category=QualityCheckCategory.SCHEMA,
        observed_value=", ".join(sorted(provided)),
        expected_value=", ".join(contract.required_fields),
    )


def _check_required_values(
    *,
    dataset_name: str,
    check_name: str,
    records: Iterable[object],
) -> QualityCheckResult:
    contract = get_dataset_contract(dataset_name)
    affected = 0
    failed_fields: list[str] = []
    for record in records:
        row_failed_fields = [
            field_name
            for field_name in contract.required_fields
            if getattr(record, field_name, None) is None
        ]
        if row_failed_fields:
            affected += 1
            failed_fields.extend(row_failed_fields)

    if affected:
        return failed_result(
            dataset_name=dataset_name,
            check_name=check_name,
            check_category=QualityCheckCategory.SCHEMA,
            observed_value=f"{affected} rows with null required fields",
            expected_value="all required fields populated",
            affected_record_count=affected,
            safe_detail=f"null required fields: {', '.join(sorted(set(failed_fields)))}",
        )

    return passed_result(
        dataset_name=dataset_name,
        check_name=check_name,
        check_category=QualityCheckCategory.SCHEMA,
        observed_value="all required fields populated",
        expected_value="all required fields populated",
    )


def _check_freshness(
    *,
    dataset_name: str,
    check_name: str,
    timestamps: Iterable[datetime],
    now_utc: datetime,
    tolerance: timedelta,
) -> QualityCheckResult:
    now = _require_aware_utc(now_utc, "now_utc")
    latest = max(timestamps, default=None)
    if latest is None:
        return failed_result(
            dataset_name=dataset_name,
            check_name=check_name,
            check_category=QualityCheckCategory.FRESHNESS,
            severity=QualitySeverity.CRITICAL,
            observed_value="no current timestamps",
            expected_value=f"latest timestamp within {tolerance}",
            affected_record_count=0,
            safe_detail=f"no current {dataset_name} timestamps available",
        )

    age = now - latest
    if age > tolerance:
        return failed_result(
            dataset_name=dataset_name,
            check_name=check_name,
            check_category=QualityCheckCategory.FRESHNESS,
            severity=QualitySeverity.ERROR,
            observed_value=str(age),
            expected_value=f"<= {tolerance}",
            affected_record_count=1,
            safe_detail=f"latest timestamp is {latest.isoformat()}",
        )

    return passed_result(
        dataset_name=dataset_name,
        check_name=check_name,
        check_category=QualityCheckCategory.FRESHNESS,
        observed_value=str(age),
        expected_value=f"<= {tolerance}",
    )


def _is_aware_utc(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() == timedelta(0)


def _require_aware_utc(value: datetime, name: str) -> datetime:
    if not _is_aware_utc(value):
        raise ValueError(f"{name} must be timezone-aware UTC")

    return value.astimezone(UTC)


def _expected_times(start: datetime, end: datetime, step: timedelta) -> list[datetime]:
    values: list[datetime] = []
    cursor = start
    while cursor < end:
        values.append(cursor)
        cursor += step

    return values


def _whole_hours(delta: timedelta) -> int | None:
    seconds = delta.total_seconds()
    if seconds % 3600 != 0:
        return None

    return int(seconds // 3600)


def _format_datetimes(values: list[datetime]) -> str:
    return ", ".join(value.isoformat() for value in values[:5])
