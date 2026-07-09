"""Tests for weather dataset quality checks."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from gridops.quality.contracts import QualityResultStatus, QualitySeverity
from gridops.quality.weather import (
    check_weather_forecast_freshness,
    check_weather_forecast_ranges,
    check_weather_forecast_required_columns,
    check_weather_forecast_required_values,
    check_weather_forecast_timestamps,
    check_weather_forecast_unique_current_source_keys,
    check_weather_forecast_valid_time_completeness,
    check_weather_observation_continuity,
    check_weather_observation_freshness,
    check_weather_observation_ranges,
    check_weather_observation_required_columns,
    check_weather_observation_required_values,
    check_weather_observation_timestamps,
    check_weather_observation_unique_current_source_keys,
)


@dataclass(slots=True)
class WeatherObservationRecord:
    source_name: str | None = "weather-observations"
    source_station_id: str | None = "TORONTO"
    source_native_timestamp: str | None = "2026-01-15T12:00:00+00:00"
    observed_at_utc: datetime = datetime(2026, 1, 15, 12, tzinfo=UTC)
    temperature_c: Decimal | None = Decimal("2.5")
    relative_humidity_percent: Decimal | None = Decimal("80")
    wind_speed_kph: Decimal | None = Decimal("12")
    precipitation_mm: Decimal | None = Decimal("0")
    source_snapshot_id: int | None = 1
    ingestion_run_id: int | None = 1
    row_hash_sha256: str | None = "a" * 64
    is_current: bool = True
    superseded_at_utc: datetime | None = None
    id: int | None = 1


@dataclass(slots=True)
class WeatherForecastRecord:
    source_name: str | None = "weather-forecasts"
    forecast_location: str | None = "TORONTO"
    source_native_issue_time: str | None = "2026-01-15T00:00:00+00:00"
    source_native_valid_time: str | None = "2026-01-15T06:00:00+00:00"
    issue_time_utc: datetime = datetime(2026, 1, 15, 0, tzinfo=UTC)
    valid_time_utc: datetime = datetime(2026, 1, 15, 6, tzinfo=UTC)
    lead_time_hours: int | None = 6
    variable_name: str | None = "temperature_c"
    variable_value: Decimal | None = Decimal("4")
    variable_unit: str | None = "C"
    source_snapshot_id: int | None = 1
    ingestion_run_id: int | None = 1
    row_hash_sha256: str | None = "b" * 64
    is_current: bool = True
    superseded_at_utc: datetime | None = None
    id: int | None = 1


def test_weather_observation_checks_pass() -> None:
    records = [_observation(), _observation(observed_at_utc=datetime(2026, 1, 15, 13, tzinfo=UTC))]

    assert check_weather_observation_required_values(records).status == QualityResultStatus.PASSED
    assert (
        check_weather_observation_unique_current_source_keys(records).status
        == QualityResultStatus.PASSED
    )
    assert check_weather_observation_ranges(records).status == QualityResultStatus.PASSED
    assert check_weather_observation_timestamps(records).status == QualityResultStatus.PASSED
    assert (
        check_weather_observation_continuity(
            records,
            station_id="TORONTO",
            window_start_utc=datetime(2026, 1, 15, 12, tzinfo=UTC),
            window_end_utc=datetime(2026, 1, 15, 14, tzinfo=UTC),
        ).status
        == QualityResultStatus.PASSED
    )
    assert (
        check_weather_observation_freshness(
            records,
            now_utc=datetime(2026, 1, 15, 14, tzinfo=UTC),
            tolerance=timedelta(hours=2),
        ).status
        == QualityResultStatus.PASSED
    )


def test_weather_observation_checks_fail() -> None:
    invalid = _observation()
    invalid.source_station_id = None
    invalid.temperature_c = Decimal("100")
    invalid.relative_humidity_percent = Decimal("120")
    invalid.wind_speed_kph = Decimal("-1")
    invalid.precipitation_mm = Decimal("-1")

    duplicate = _observation()

    assert (
        check_weather_observation_required_columns({"source_name"}).status
        == QualityResultStatus.FAILED
    )
    assert check_weather_observation_required_values([invalid]).status == QualityResultStatus.FAILED
    assert (
        check_weather_observation_unique_current_source_keys([duplicate, duplicate]).status
        == QualityResultStatus.FAILED
    )
    assert check_weather_observation_ranges([invalid]).status == QualityResultStatus.FAILED
    assert (
        check_weather_observation_continuity(
            [_observation()],
            station_id="TORONTO",
            window_start_utc=datetime(2026, 1, 15, 12, tzinfo=UTC),
            window_end_utc=datetime(2026, 1, 15, 14, tzinfo=UTC),
        ).status
        == QualityResultStatus.FAILED
    )
    stale = check_weather_observation_freshness(
        [_observation()],
        now_utc=datetime(2026, 1, 16, 12, tzinfo=UTC),
        tolerance=timedelta(hours=2),
    )
    assert stale.status == QualityResultStatus.FAILED
    assert stale.severity == QualitySeverity.ERROR


def test_weather_observation_timestamp_failure() -> None:
    invalid = _observation(observed_at_utc=datetime(2026, 1, 15, 12))

    result = check_weather_observation_timestamps([invalid])

    assert result.status == QualityResultStatus.FAILED


def test_weather_forecast_checks_pass() -> None:
    records = [
        _forecast(valid_time_utc=datetime(2026, 1, 15, 6, tzinfo=UTC), lead_time_hours=6),
        _forecast(valid_time_utc=datetime(2026, 1, 15, 9, tzinfo=UTC), lead_time_hours=9),
    ]

    assert check_weather_forecast_required_values(records).status == QualityResultStatus.PASSED
    assert (
        check_weather_forecast_unique_current_source_keys(records).status
        == QualityResultStatus.PASSED
    )
    assert check_weather_forecast_ranges(records).status == QualityResultStatus.PASSED
    assert check_weather_forecast_timestamps(records).status == QualityResultStatus.PASSED
    assert (
        check_weather_forecast_valid_time_completeness(
            records,
            forecast_location="TORONTO",
            variable_name="temperature_c",
            issue_time_utc=datetime(2026, 1, 15, 0, tzinfo=UTC),
            expected_valid_times_utc=[
                datetime(2026, 1, 15, 6, tzinfo=UTC),
                datetime(2026, 1, 15, 9, tzinfo=UTC),
            ],
        ).status
        == QualityResultStatus.PASSED
    )
    assert (
        check_weather_forecast_freshness(
            records,
            now_utc=datetime(2026, 1, 15, 12, tzinfo=UTC),
            tolerance=timedelta(hours=24),
        ).status
        == QualityResultStatus.PASSED
    )


def test_weather_forecast_checks_fail() -> None:
    invalid = _forecast()
    invalid.variable_name = None
    invalid.variable_value = Decimal("2000")
    invalid.valid_time_utc = datetime(2026, 1, 14, 23, tzinfo=UTC)
    invalid.lead_time_hours = 6

    duplicate = _forecast()

    assert (
        check_weather_forecast_required_columns({"source_name"}).status
        == QualityResultStatus.FAILED
    )
    assert check_weather_forecast_required_values([invalid]).status == QualityResultStatus.FAILED
    assert (
        check_weather_forecast_unique_current_source_keys([duplicate, duplicate]).status
        == QualityResultStatus.FAILED
    )
    assert check_weather_forecast_ranges([invalid]).status == QualityResultStatus.FAILED
    assert check_weather_forecast_timestamps([invalid]).status == QualityResultStatus.FAILED
    assert (
        check_weather_forecast_valid_time_completeness(
            [_forecast()],
            forecast_location="TORONTO",
            variable_name="temperature_c",
            issue_time_utc=datetime(2026, 1, 15, 0, tzinfo=UTC),
            expected_valid_times_utc=[
                datetime(2026, 1, 15, 6, tzinfo=UTC),
                datetime(2026, 1, 15, 9, tzinfo=UTC),
            ],
        ).status
        == QualityResultStatus.FAILED
    )
    assert (
        check_weather_forecast_freshness(
            [_forecast()],
            now_utc=datetime(2026, 1, 17, 0, tzinfo=UTC),
            tolerance=timedelta(hours=12),
        ).status
        == QualityResultStatus.FAILED
    )


def _observation(**overrides: object) -> WeatherObservationRecord:
    record = WeatherObservationRecord()
    for key, value in overrides.items():
        setattr(record, key, value)
    return record


def _forecast(**overrides: object) -> WeatherForecastRecord:
    record = WeatherForecastRecord()
    for key, value in overrides.items():
        setattr(record, key, value)
    return record
