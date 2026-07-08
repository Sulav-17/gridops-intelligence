"""Parser for fixture-backed IESO hourly demand payloads."""

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from io import StringIO

from gridops.ingestion.hashing import sha256_bytes
from gridops.time_utils import TORONTO_TIME_ZONE, ieso_hour_ending_to_utc


@dataclass(frozen=True, slots=True)
class ParsedIesoDemandRecord:
    """Normalized IESO demand record with preserved source-native fields."""

    source_service_date: str
    source_hour_ending: int
    interval_start_utc: datetime
    interval_end_utc: datetime
    demand_mw: Decimal
    row_hash_sha256: str


def parse_ieso_hourly_demand(payload: bytes) -> list[ParsedIesoDemandRecord]:
    """Parse an IESO hourly demand CSV fixture into typed records."""

    text = payload.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    _require_columns(reader.fieldnames)

    records: list[ParsedIesoDemandRecord] = []
    for line_number, row in enumerate(reader, start=2):
        source_service_date = _required_value(row, "service_date", line_number)
        source_hour_ending = _parse_hour_ending(row, line_number)
        demand_mw = _parse_demand_mw(row, line_number)
        service_date = _parse_service_date(source_service_date, line_number)
        interval_end_utc = ieso_hour_ending_to_utc(service_date, source_hour_ending)
        interval_start_utc = interval_end_utc - timedelta(hours=1)
        row_hash_sha256 = _row_hash(
            source_service_date=source_service_date,
            source_hour_ending=source_hour_ending,
            interval_start_utc=interval_start_utc,
            interval_end_utc=interval_end_utc,
            demand_mw=demand_mw,
        )
        records.append(
            ParsedIesoDemandRecord(
                source_service_date=source_service_date,
                source_hour_ending=source_hour_ending,
                interval_start_utc=interval_start_utc,
                interval_end_utc=interval_end_utc,
                demand_mw=demand_mw,
                row_hash_sha256=row_hash_sha256,
            )
        )

    return records


def _require_columns(fieldnames: Sequence[str] | None) -> None:
    required = {"service_date", "hour_ending", "demand_mw"}
    provided = set(fieldnames or [])
    missing = sorted(required - provided)

    if missing:
        raise ValueError(f"IESO demand fixture is missing columns: {', '.join(missing)}")


def _required_value(row: dict[str, str], column_name: str, line_number: int) -> str:
    value = row.get(column_name, "").strip()

    if not value:
        raise ValueError(f"missing {column_name} on line {line_number}")

    return value


def _parse_service_date(source_service_date: str, line_number: int) -> datetime:
    try:
        parsed_date = datetime.strptime(source_service_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"invalid service_date on line {line_number}") from exc

    return datetime(
        parsed_date.year,
        parsed_date.month,
        parsed_date.day,
        tzinfo=TORONTO_TIME_ZONE,
    )


def _parse_hour_ending(row: dict[str, str], line_number: int) -> int:
    raw_value = _required_value(row, "hour_ending", line_number)

    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"invalid hour_ending on line {line_number}") from exc


def _parse_demand_mw(row: dict[str, str], line_number: int) -> Decimal:
    raw_value = _required_value(row, "demand_mw", line_number)

    try:
        demand_mw = Decimal(raw_value)
    except InvalidOperation as exc:
        raise ValueError(f"invalid demand_mw on line {line_number}") from exc

    if demand_mw < 0:
        raise ValueError(f"demand_mw must be nonnegative on line {line_number}")

    return demand_mw


def _row_hash(
    *,
    source_service_date: str,
    source_hour_ending: int,
    interval_start_utc: datetime,
    interval_end_utc: datetime,
    demand_mw: Decimal,
) -> str:
    payload = "|".join(
        (
            source_service_date,
            str(source_hour_ending),
            interval_start_utc.isoformat(),
            interval_end_utc.isoformat(),
            str(demand_mw.normalize()),
        )
    ).encode("utf-8")
    return sha256_bytes(payload)
