"""Parser for fixture-backed weather observation payloads."""

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import StringIO

from gridops.ingestion.hashing import sha256_bytes
from gridops.time_utils import to_utc


@dataclass(frozen=True, slots=True)
class ParsedWeatherObservationRecord:
    """Normalized weather observation with preserved source-native fields."""

    source_name: str
    source_station_id: str
    source_native_timestamp: str
    observed_at_utc: datetime
    temperature_c: Decimal | None
    relative_humidity_percent: Decimal | None
    wind_speed_kph: Decimal | None
    precipitation_mm: Decimal | None
    row_hash_sha256: str


def parse_weather_observations(
    payload: bytes, *, source_name: str
) -> list[ParsedWeatherObservationRecord]:
    """Parse a weather observation CSV fixture into typed records."""

    text = payload.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    _require_columns(reader.fieldnames)

    records: list[ParsedWeatherObservationRecord] = []
    for line_number, row in enumerate(reader, start=2):
        station_id = _required_value(row, "station_id", line_number)
        source_native_timestamp = _required_value(row, "observed_at", line_number)
        observed_at_utc = _parse_aware_timestamp(
            source_native_timestamp, "observed_at", line_number
        )
        temperature_c = _parse_optional_decimal(row, "temperature_c", line_number)
        relative_humidity_percent = _parse_optional_decimal(
            row,
            "relative_humidity_percent",
            line_number,
        )
        wind_speed_kph = _parse_optional_decimal(row, "wind_speed_kph", line_number)
        precipitation_mm = _parse_optional_decimal(row, "precipitation_mm", line_number)
        row_hash_sha256 = _row_hash(
            source_name=source_name,
            station_id=station_id,
            source_native_timestamp=source_native_timestamp,
            observed_at_utc=observed_at_utc,
            temperature_c=temperature_c,
            relative_humidity_percent=relative_humidity_percent,
            wind_speed_kph=wind_speed_kph,
            precipitation_mm=precipitation_mm,
        )
        records.append(
            ParsedWeatherObservationRecord(
                source_name=source_name,
                source_station_id=station_id,
                source_native_timestamp=source_native_timestamp,
                observed_at_utc=observed_at_utc,
                temperature_c=temperature_c,
                relative_humidity_percent=relative_humidity_percent,
                wind_speed_kph=wind_speed_kph,
                precipitation_mm=precipitation_mm,
                row_hash_sha256=row_hash_sha256,
            )
        )

    return records


def _require_columns(fieldnames: Sequence[str] | None) -> None:
    required = {
        "station_id",
        "observed_at",
        "temperature_c",
        "relative_humidity_percent",
        "wind_speed_kph",
        "precipitation_mm",
    }
    provided = set(fieldnames or [])
    missing = sorted(required - provided)

    if missing:
        raise ValueError(f"weather observation fixture is missing columns: {', '.join(missing)}")


def _required_value(row: dict[str, str], column_name: str, line_number: int) -> str:
    value = row.get(column_name, "").strip()

    if not value:
        raise ValueError(f"missing {column_name} on line {line_number}")

    return value


def _parse_aware_timestamp(raw_value: str, column_name: str, line_number: int) -> datetime:
    try:
        parsed = datetime.fromisoformat(raw_value)
    except ValueError as exc:
        raise ValueError(f"invalid {column_name} on line {line_number}") from exc

    try:
        return to_utc(parsed)
    except ValueError as exc:
        raise ValueError(
            f"{column_name} must include timezone information on line {line_number}"
        ) from exc


def _parse_optional_decimal(
    row: dict[str, str],
    column_name: str,
    line_number: int,
) -> Decimal | None:
    raw_value = row.get(column_name, "").strip()

    if not raw_value:
        return None

    try:
        return Decimal(raw_value)
    except InvalidOperation as exc:
        raise ValueError(f"invalid {column_name} on line {line_number}") from exc


def _decimal_for_hash(value: Decimal | None) -> str:
    return "" if value is None else str(value.normalize())


def _row_hash(
    *,
    source_name: str,
    station_id: str,
    source_native_timestamp: str,
    observed_at_utc: datetime,
    temperature_c: Decimal | None,
    relative_humidity_percent: Decimal | None,
    wind_speed_kph: Decimal | None,
    precipitation_mm: Decimal | None,
) -> str:
    payload = "|".join(
        (
            source_name,
            station_id,
            source_native_timestamp,
            observed_at_utc.isoformat(),
            _decimal_for_hash(temperature_c),
            _decimal_for_hash(relative_humidity_percent),
            _decimal_for_hash(wind_speed_kph),
            _decimal_for_hash(precipitation_mm),
        )
    ).encode("utf-8")
    return sha256_bytes(payload)
