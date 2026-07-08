"""Loader for parsed archived weather forecast records."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from gridops.ingestion.parsers.weather_forecasts import ParsedWeatherForecastRecord
from gridops.ingestion.runs import utc_now
from gridops.models import IngestionRun, RawSnapshot, WeatherForecast


@dataclass(frozen=True, slots=True)
class WeatherForecastLoadResult:
    """Summarize an archived weather forecast load operation."""

    records_seen: int
    records_inserted: int
    records_unchanged: int
    records_superseded: int


def load_weather_forecasts(
    session: Session,
    *,
    records: list[ParsedWeatherForecastRecord],
    ingestion_run: IngestionRun,
    raw_snapshot: RawSnapshot,
    superseded_at_utc: datetime | None = None,
) -> WeatherForecastLoadResult:
    """Load parsed archived weather forecasts idempotently."""

    inserted = 0
    unchanged = 0
    superseded = 0
    revision_timestamp = superseded_at_utc if superseded_at_utc is not None else utc_now()

    for record in records:
        current = _get_current_record(session, record)

        if current is not None and current.row_hash_sha256 == record.row_hash_sha256:
            unchanged += 1
            continue

        reusable_revision = _get_existing_revision(session, record)

        if current is not None:
            current.is_current = False
            current.superseded_at_utc = revision_timestamp
            superseded += 1

        if reusable_revision is not None:
            reusable_revision.is_current = True
            reusable_revision.superseded_at_utc = None
            reusable_revision.ingestion_run_id = ingestion_run.id
            reusable_revision.source_snapshot_id = raw_snapshot.id
            continue

        session.add(
            WeatherForecast(
                source_name=record.source_name,
                forecast_location=record.forecast_location,
                source_native_issue_time=record.source_native_issue_time,
                source_native_valid_time=record.source_native_valid_time,
                issue_time_utc=record.issue_time_utc,
                valid_time_utc=record.valid_time_utc,
                lead_time_hours=record.lead_time_hours,
                variable_name=record.variable_name,
                variable_value=record.variable_value,
                variable_unit=record.variable_unit,
                source_snapshot_id=raw_snapshot.id,
                ingestion_run_id=ingestion_run.id,
                row_hash_sha256=record.row_hash_sha256,
                is_current=True,
                superseded_at_utc=None,
            )
        )
        inserted += 1

    session.flush()

    return WeatherForecastLoadResult(
        records_seen=len(records),
        records_inserted=inserted,
        records_unchanged=unchanged,
        records_superseded=superseded,
    )


def _get_current_record(
    session: Session,
    record: ParsedWeatherForecastRecord,
) -> WeatherForecast | None:
    return session.execute(
        select(WeatherForecast).where(
            WeatherForecast.source_name == record.source_name,
            WeatherForecast.forecast_location == record.forecast_location,
            WeatherForecast.issue_time_utc == record.issue_time_utc,
            WeatherForecast.valid_time_utc == record.valid_time_utc,
            WeatherForecast.variable_name == record.variable_name,
            WeatherForecast.is_current.is_(True),
        )
    ).scalar_one_or_none()


def _get_existing_revision(
    session: Session,
    record: ParsedWeatherForecastRecord,
) -> WeatherForecast | None:
    return session.execute(
        select(WeatherForecast).where(
            WeatherForecast.source_name == record.source_name,
            WeatherForecast.forecast_location == record.forecast_location,
            WeatherForecast.issue_time_utc == record.issue_time_utc,
            WeatherForecast.valid_time_utc == record.valid_time_utc,
            WeatherForecast.variable_name == record.variable_name,
            WeatherForecast.row_hash_sha256 == record.row_hash_sha256,
        )
    ).scalar_one_or_none()
