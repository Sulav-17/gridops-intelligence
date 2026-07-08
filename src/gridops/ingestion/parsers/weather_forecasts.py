"""Parser for fixture-backed archived weather forecast payloads."""

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import StringIO

from gridops.ingestion.hashing import sha256_bytes
from gridops.time_utils import to_utc


@dataclass(frozen=True, slots=True)
class ParsedWeatherForecastRecord:
    """Normalized weather forecast with preserved source-native fields."""

    source_name: str
    forecast_location: str
    source_native_issue_time: str
    source_native_valid_time: str
    issue_time_utc: datetime
    valid_time_utc: datetime
    lead_time_hours: int | None
    variable_name: str
    variable_value: Decimal
    variable_unit: str | None
    row_hash_sha256: str


def parse_weather_forecasts(
    payload: bytes, *, source_name: str
) -> list[ParsedWeatherForecastRecord]:
    """Parse an archived weather forecast CSV fixture into typed records."""

    text = payload.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    _require_columns(reader.fieldnames)

    records: list[ParsedWeatherForecastRecord] = []
    for line_number, row in enumerate(reader, start=2):
        location = _required_value(row, "location", line_number)
        source_native_issue_time = _required_value(row, "issue_time", line_number)
        source_native_valid_time = _required_value(row, "valid_time", line_number)
        issue_time_utc = _parse_aware_timestamp(source_native_issue_time, "issue_time", line_number)
        valid_time_utc = _parse_aware_timestamp(source_native_valid_time, "valid_time", line_number)
        lead_time_hours = _lead_time_hours(issue_time_utc, valid_time_utc)
        variable_name = _required_value(row, "variable_name", line_number)
        variable_value = _parse_required_decimal(row, "variable_value", line_number)
        variable_unit = row.get("variable_unit", "").strip() or None
        row_hash_sha256 = _row_hash(
            source_name=source_name,
            location=location,
            source_native_issue_time=source_native_issue_time,
            source_native_valid_time=source_native_valid_time,
            issue_time_utc=issue_time_utc,
            valid_time_utc=valid_time_utc,
            lead_time_hours=lead_time_hours,
            variable_name=variable_name,
            variable_value=variable_value,
            variable_unit=variable_unit,
        )
        records.append(
            ParsedWeatherForecastRecord(
                source_name=source_name,
                forecast_location=location,
                source_native_issue_time=source_native_issue_time,
                source_native_valid_time=source_native_valid_time,
                issue_time_utc=issue_time_utc,
                valid_time_utc=valid_time_utc,
                lead_time_hours=lead_time_hours,
                variable_name=variable_name,
                variable_value=variable_value,
                variable_unit=variable_unit,
                row_hash_sha256=row_hash_sha256,
            )
        )

    return records


def _require_columns(fieldnames: Sequence[str] | None) -> None:
    required = {
        "location",
        "issue_time",
        "valid_time",
        "variable_name",
        "variable_value",
        "variable_unit",
    }
    provided = set(fieldnames or [])
    missing = sorted(required - provided)

    if missing:
        raise ValueError(f"weather forecast fixture is missing columns: {', '.join(missing)}")


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


def _parse_required_decimal(
    row: dict[str, str],
    column_name: str,
    line_number: int,
) -> Decimal:
    raw_value = _required_value(row, column_name, line_number)

    try:
        return Decimal(raw_value)
    except InvalidOperation as exc:
        raise ValueError(f"invalid {column_name} on line {line_number}") from exc


def _lead_time_hours(issue_time_utc: datetime, valid_time_utc: datetime) -> int | None:
    seconds = (valid_time_utc - issue_time_utc).total_seconds()

    if seconds % 3600 != 0:
        return None

    return int(seconds // 3600)


def _row_hash(
    *,
    source_name: str,
    location: str,
    source_native_issue_time: str,
    source_native_valid_time: str,
    issue_time_utc: datetime,
    valid_time_utc: datetime,
    lead_time_hours: int | None,
    variable_name: str,
    variable_value: Decimal,
    variable_unit: str | None,
) -> str:
    payload = "|".join(
        (
            source_name,
            location,
            source_native_issue_time,
            source_native_valid_time,
            issue_time_utc.isoformat(),
            valid_time_utc.isoformat(),
            "" if lead_time_hours is None else str(lead_time_hours),
            variable_name,
            str(variable_value.normalize()),
            variable_unit or "",
        )
    ).encode("utf-8")
    return sha256_bytes(payload)
