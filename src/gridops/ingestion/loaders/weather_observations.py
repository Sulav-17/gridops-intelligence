"""Loader for parsed weather observation records."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from gridops.ingestion.parsers.weather_observations import ParsedWeatherObservationRecord
from gridops.ingestion.runs import utc_now
from gridops.models import IngestionRun, RawSnapshot, WeatherObservation


@dataclass(frozen=True, slots=True)
class WeatherObservationLoadResult:
    """Summarize a weather observation load operation."""

    records_seen: int
    records_inserted: int
    records_unchanged: int
    records_superseded: int


def load_weather_observations(
    session: Session,
    *,
    records: list[ParsedWeatherObservationRecord],
    ingestion_run: IngestionRun,
    raw_snapshot: RawSnapshot,
    superseded_at_utc: datetime | None = None,
) -> WeatherObservationLoadResult:
    """Load parsed weather observations idempotently."""

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
            WeatherObservation(
                source_name=record.source_name,
                source_station_id=record.source_station_id,
                source_native_timestamp=record.source_native_timestamp,
                observed_at_utc=record.observed_at_utc,
                temperature_c=record.temperature_c,
                relative_humidity_percent=record.relative_humidity_percent,
                wind_speed_kph=record.wind_speed_kph,
                precipitation_mm=record.precipitation_mm,
                source_snapshot_id=raw_snapshot.id,
                ingestion_run_id=ingestion_run.id,
                row_hash_sha256=record.row_hash_sha256,
                is_current=True,
                superseded_at_utc=None,
            )
        )
        inserted += 1

    session.flush()

    return WeatherObservationLoadResult(
        records_seen=len(records),
        records_inserted=inserted,
        records_unchanged=unchanged,
        records_superseded=superseded,
    )


def _get_current_record(
    session: Session,
    record: ParsedWeatherObservationRecord,
) -> WeatherObservation | None:
    return session.execute(
        select(WeatherObservation).where(
            WeatherObservation.source_name == record.source_name,
            WeatherObservation.source_station_id == record.source_station_id,
            WeatherObservation.observed_at_utc == record.observed_at_utc,
            WeatherObservation.is_current.is_(True),
        )
    ).scalar_one_or_none()


def _get_existing_revision(
    session: Session,
    record: ParsedWeatherObservationRecord,
) -> WeatherObservation | None:
    return session.execute(
        select(WeatherObservation).where(
            WeatherObservation.source_name == record.source_name,
            WeatherObservation.source_station_id == record.source_station_id,
            WeatherObservation.observed_at_utc == record.observed_at_utc,
            WeatherObservation.row_hash_sha256 == record.row_hash_sha256,
        )
    ).scalar_one_or_none()
