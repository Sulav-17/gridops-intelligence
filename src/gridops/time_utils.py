"""Time utilities and IESO hour-ending contract for GridOps Intelligence."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

TORONTO_TIME_ZONE_NAME = "America/Toronto"
TORONTO_TIME_ZONE = ZoneInfo(TORONTO_TIME_ZONE_NAME)

MIN_IESO_HOUR_ENDING = 1
MAX_IESO_HOUR_ENDING = 24


def require_aware_datetime(value: datetime) -> datetime:
    """Return an aware datetime or reject a naive value."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")

    return value


def to_utc(value: datetime) -> datetime:
    """Convert an aware datetime to canonical UTC."""

    return require_aware_datetime(value).astimezone(UTC)


def utc_to_toronto(value: datetime) -> datetime:
    """Convert an aware datetime to America/Toronto local time."""

    return to_utc(value).astimezone(TORONTO_TIME_ZONE)


def toronto_to_utc(value: datetime, *, fold: int | None = None) -> datetime:
    """Convert America/Toronto local time to UTC.

    Ambiguous fall-back wall times require an explicit ``fold`` value:
    ``0`` selects the first occurrence and ``1`` selects the second. Nonexistent
    spring-forward wall times are rejected.
    """

    require_aware_datetime(value)
    if value.tzinfo != TORONTO_TIME_ZONE:
        raise ValueError(f"datetime must use {TORONTO_TIME_ZONE_NAME}")

    naive_value = value.replace(tzinfo=None)

    if _is_nonexistent_toronto_time(naive_value):
        raise ValueError("datetime is nonexistent in America/Toronto")

    if _is_ambiguous_toronto_time(naive_value):
        if fold not in (0, 1):
            raise ValueError("ambiguous America/Toronto datetime requires fold 0 or 1")
        value = value.replace(fold=fold)

    return value.astimezone(UTC)


def validate_ieso_hour_ending(hour_ending: int) -> int:
    """Validate an IESO hour-ending value in the inclusive range 1 through 24."""

    if not MIN_IESO_HOUR_ENDING <= hour_ending <= MAX_IESO_HOUR_ENDING:
        raise ValueError("IESO hour-ending must be between 1 and 24")

    return hour_ending


def ieso_hour_ending_to_utc(service_date: datetime, hour_ending: int) -> datetime:
    """Convert an IESO service date and hour-ending value to UTC.

    IESO hour-ending values label the end of an operating hour in Toronto local
    time. For example, hour-ending 1 on a service date maps to 01:00 local time
    on that date. Hour-ending 24 maps to 00:00 local time on the following
    calendar date.

    The service date must be an aware ``America/Toronto`` datetime at local
    midnight. This function rejects nonexistent or ambiguous local endpoint
    times rather than guessing a daylight-saving interpretation.
    """

    validate_ieso_hour_ending(hour_ending)
    require_aware_datetime(service_date)

    if service_date.tzinfo != TORONTO_TIME_ZONE:
        raise ValueError(f"service_date must use {TORONTO_TIME_ZONE_NAME}")

    if service_date.time() != datetime.min.time():
        raise ValueError("service_date must be local midnight")

    naive_endpoint = service_date.replace(tzinfo=None) + timedelta(hours=hour_ending)
    endpoint = naive_endpoint.replace(tzinfo=TORONTO_TIME_ZONE)

    return toronto_to_utc(endpoint)


def _is_ambiguous_toronto_time(naive_value: datetime) -> bool:
    first = naive_value.replace(tzinfo=TORONTO_TIME_ZONE, fold=0)
    second = naive_value.replace(tzinfo=TORONTO_TIME_ZONE, fold=1)

    return first.utcoffset() != second.utcoffset() and _round_trips(first) and _round_trips(second)


def _is_nonexistent_toronto_time(naive_value: datetime) -> bool:
    first = naive_value.replace(tzinfo=TORONTO_TIME_ZONE, fold=0)
    second = naive_value.replace(tzinfo=TORONTO_TIME_ZONE, fold=1)

    return not _round_trips(first) and not _round_trips(second)


def _round_trips(value: datetime) -> bool:
    naive_value = value.replace(tzinfo=None)
    round_tripped = value.astimezone(UTC).astimezone(TORONTO_TIME_ZONE)

    return round_tripped.replace(tzinfo=None) == naive_value
