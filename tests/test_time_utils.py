"""Tests for time-zone and IESO hour-ending utilities."""

from datetime import UTC, datetime

import pytest

from gridops.time_utils import (
    TORONTO_TIME_ZONE,
    ieso_hour_ending_to_utc,
    require_aware_datetime,
    to_utc,
    toronto_to_utc,
    utc_to_toronto,
    validate_ieso_hour_ending,
)


def test_naive_datetimes_are_rejected() -> None:
    """Naive datetimes are never accepted silently."""

    with pytest.raises(ValueError, match="timezone-aware"):
        require_aware_datetime(datetime(2026, 1, 1, 12))


def test_canonical_timestamps_are_timezone_aware_utc() -> None:
    """Canonical conversion returns aware UTC datetimes."""

    local_time = datetime(2026, 1, 1, 7, tzinfo=TORONTO_TIME_ZONE)

    converted = to_utc(local_time)

    assert converted == datetime(2026, 1, 1, 12, tzinfo=UTC)
    assert converted.tzinfo is UTC


def test_utc_to_toronto_conversion() -> None:
    """UTC timestamps convert to America/Toronto local time."""

    utc_time = datetime(2026, 7, 1, 16, tzinfo=UTC)

    converted = utc_to_toronto(utc_time)

    assert converted == datetime(2026, 7, 1, 12, tzinfo=TORONTO_TIME_ZONE)
    assert converted.tzinfo == TORONTO_TIME_ZONE


def test_toronto_to_utc_conversion() -> None:
    """America/Toronto timestamps convert to UTC."""

    toronto_time = datetime(2026, 7, 1, 12, tzinfo=TORONTO_TIME_ZONE)

    converted = toronto_to_utc(toronto_time)

    assert converted == datetime(2026, 7, 1, 16, tzinfo=UTC)


def test_dst_spring_forward_nonexistent_time_is_rejected() -> None:
    """Spring-forward local wall times that never occur are rejected."""

    nonexistent_time = datetime(2026, 3, 8, 2, 30, tzinfo=TORONTO_TIME_ZONE)

    with pytest.raises(ValueError, match="nonexistent"):
        toronto_to_utc(nonexistent_time)


def test_dst_fall_back_ambiguous_time_requires_explicit_fold() -> None:
    """Fall-back local wall times require an explicit occurrence."""

    ambiguous_time = datetime(2026, 11, 1, 1, 30, tzinfo=TORONTO_TIME_ZONE)

    with pytest.raises(ValueError, match="ambiguous"):
        toronto_to_utc(ambiguous_time)

    assert toronto_to_utc(ambiguous_time, fold=0) == datetime(2026, 11, 1, 5, 30, tzinfo=UTC)
    assert toronto_to_utc(ambiguous_time, fold=1) == datetime(2026, 11, 1, 6, 30, tzinfo=UTC)


@pytest.mark.parametrize("hour_ending", [1, 12, 24])
def test_ieso_hour_ending_values_are_validated(hour_ending: int) -> None:
    """IESO hour-ending values are valid from 1 through 24."""

    assert validate_ieso_hour_ending(hour_ending) == hour_ending


@pytest.mark.parametrize("hour_ending", [0, 25])
def test_invalid_ieso_hour_ending_values_are_rejected(hour_ending: int) -> None:
    """Out-of-range IESO hour-ending values are rejected."""

    with pytest.raises(ValueError, match="hour-ending"):
        validate_ieso_hour_ending(hour_ending)


def test_ieso_hour_ending_converts_local_endpoint_to_utc() -> None:
    """Hour-ending labels the end of an operating hour in Toronto local time."""

    service_date = datetime(2026, 1, 15, tzinfo=TORONTO_TIME_ZONE)

    assert ieso_hour_ending_to_utc(service_date, 1) == datetime(2026, 1, 15, 6, tzinfo=UTC)
    assert ieso_hour_ending_to_utc(service_date, 24) == datetime(2026, 1, 16, 5, tzinfo=UTC)


def test_ieso_hour_ending_rejects_non_midnight_service_date() -> None:
    """IESO conversion requires a local service date at midnight."""

    service_date = datetime(2026, 1, 15, 12, tzinfo=TORONTO_TIME_ZONE)

    with pytest.raises(ValueError, match="midnight"):
        ieso_hour_ending_to_utc(service_date, 1)


def test_ieso_hour_ending_rejects_nonexistent_endpoint() -> None:
    """IESO conversion does not guess spring-forward endpoint behavior."""

    service_date = datetime(2026, 3, 8, tzinfo=TORONTO_TIME_ZONE)

    with pytest.raises(ValueError, match="nonexistent"):
        ieso_hour_ending_to_utc(service_date, 2)


def test_ieso_hour_ending_rejects_ambiguous_endpoint() -> None:
    """IESO conversion does not guess fall-back endpoint behavior."""

    service_date = datetime(2026, 11, 1, tzinfo=TORONTO_TIME_ZONE)

    with pytest.raises(ValueError, match="ambiguous"):
        ieso_hour_ending_to_utc(service_date, 1)
