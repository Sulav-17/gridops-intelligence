"""Tests for fixture-backed weather ingestion."""

from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from gridops.config import Settings
from gridops.database import Base, make_engine, make_session_factory
from gridops.ingestion.loaders.weather_forecasts import (
    WeatherForecastLoadResult,
    load_weather_forecasts,
)
from gridops.ingestion.loaders.weather_observations import (
    WeatherObservationLoadResult,
    load_weather_observations,
)
from gridops.ingestion.parsers.weather_forecasts import (
    ParsedWeatherForecastRecord,
    parse_weather_forecasts,
)
from gridops.ingestion.parsers.weather_observations import (
    ParsedWeatherObservationRecord,
    parse_weather_observations,
)
from gridops.ingestion.raw_store import RawSnapshotMetadata, RawSnapshotStore, persist_raw_snapshot
from gridops.ingestion.runs import start_ingestion_run
from gridops.models import WeatherForecast, WeatherObservation
from gridops.sources import get_source_definition

TEST_DATABASE_URL = "postgresql+psycopg://gridops:gridops@localhost:55432/gridops_test"
FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "ingestion" / "weather"


@pytest.fixture
def live_postgres_engine() -> Generator[Engine, None, None]:
    """Create an engine for the Docker-backed test database."""

    settings = Settings(database_url=SecretStr(TEST_DATABASE_URL))
    engine = make_engine(settings)

    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def clean_session_factory(
    live_postgres_engine: Engine,
) -> Generator[sessionmaker[Session], None, None]:
    """Create a clean M02 schema for weather loader tests."""

    Base.metadata.drop_all(live_postgres_engine)
    Base.metadata.create_all(live_postgres_engine)

    try:
        yield make_session_factory(live_postgres_engine)
    finally:
        Base.metadata.drop_all(live_postgres_engine)


def test_weather_observation_parser_preserves_native_and_normalizes_utc() -> None:
    """Observation fixtures use timezone-aware source timestamps."""

    payload = (FIXTURE_ROOT / "observations_sample.csv").read_bytes()

    records = parse_weather_observations(payload, source_name="weather-observations")

    assert len(records) == 2
    assert records[0].source_station_id == "TORONTO-CITY"
    assert records[0].source_native_timestamp == "2026-01-15T07:00:00-05:00"
    assert records[0].observed_at_utc == datetime(2026, 1, 15, 12, tzinfo=UTC)
    assert records[0].temperature_c == Decimal("-4.5")
    assert len(records[0].row_hash_sha256) == 64


def test_weather_forecast_parser_preserves_times_and_lead_hour() -> None:
    """Forecast fixtures preserve issue/valid strings and derive whole-hour lead time."""

    payload = (FIXTURE_ROOT / "forecasts_sample.csv").read_bytes()

    records = parse_weather_forecasts(payload, source_name="weather-forecasts")

    assert len(records) == 2
    assert records[0].forecast_location == "TORONTO"
    assert records[0].source_native_issue_time == "2026-01-15T00:00:00-05:00"
    assert records[0].source_native_valid_time == "2026-01-15T06:00:00-05:00"
    assert records[0].issue_time_utc == datetime(2026, 1, 15, 5, tzinfo=UTC)
    assert records[0].valid_time_utc == datetime(2026, 1, 15, 11, tzinfo=UTC)
    assert records[0].lead_time_hours == 6
    assert records[0].variable_value == Decimal("-5.2")
    assert len(records[0].row_hash_sha256) == 64


@pytest.mark.integration
def test_weather_observation_loader_is_idempotent(
    clean_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """Loading the same observation fixture twice does not duplicate records."""

    payload = (FIXTURE_ROOT / "observations_sample.csv").read_bytes()
    records = parse_weather_observations(payload, source_name="weather-observations")

    with clean_session_factory() as session:
        first = _persist_and_load_observations(session, tmp_path, payload, records)
        second = _persist_and_load_observations(session, tmp_path, payload, records)
        session.commit()
        rows = session.scalars(select(WeatherObservation)).all()

    assert first.records_inserted == 2
    assert second.records_inserted == 0
    assert second.records_unchanged == 2
    assert len(rows) == 2
    assert all(row.is_current for row in rows)


@pytest.mark.integration
def test_weather_observation_loader_preserves_changed_record_revision(
    clean_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """Changed observation values create a new current revision."""

    original_payload = (FIXTURE_ROOT / "observations_sample.csv").read_bytes()
    revised_payload = (FIXTURE_ROOT / "observations_revised.csv").read_bytes()
    original_records = parse_weather_observations(
        original_payload, source_name="weather-observations"
    )
    revised_records = parse_weather_observations(
        revised_payload, source_name="weather-observations"
    )
    superseded_at = datetime(2026, 7, 8, 12, tzinfo=UTC)

    with clean_session_factory() as session:
        _persist_and_load_observations(session, tmp_path, original_payload, original_records)
        result = _persist_and_load_observations(
            session,
            tmp_path,
            revised_payload,
            revised_records,
            superseded_at_utc=superseded_at,
        )
        session.commit()
        rows = session.scalars(select(WeatherObservation).order_by(WeatherObservation.id)).all()
        revised_key_rows = [
            row for row in rows if row.observed_at_utc == datetime(2026, 1, 15, 13, tzinfo=UTC)
        ]

    assert result.records_inserted == 1
    assert result.records_unchanged == 1
    assert result.records_superseded == 1
    assert len(rows) == 3
    assert [row.is_current for row in revised_key_rows] == [False, True]
    assert revised_key_rows[0].superseded_at_utc == superseded_at
    assert revised_key_rows[0].temperature_c == Decimal("-3.800")
    assert revised_key_rows[1].temperature_c == Decimal("-3.100")


@pytest.mark.integration
def test_weather_forecast_loader_is_idempotent(
    clean_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """Loading the same forecast fixture twice does not duplicate records."""

    payload = (FIXTURE_ROOT / "forecasts_sample.csv").read_bytes()
    records = parse_weather_forecasts(payload, source_name="weather-forecasts")

    with clean_session_factory() as session:
        first = _persist_and_load_forecasts(session, tmp_path, payload, records)
        second = _persist_and_load_forecasts(session, tmp_path, payload, records)
        session.commit()
        rows = session.scalars(select(WeatherForecast)).all()

    assert first.records_inserted == 2
    assert second.records_inserted == 0
    assert second.records_unchanged == 2
    assert len(rows) == 2
    assert all(row.is_current for row in rows)


@pytest.mark.integration
def test_weather_forecast_loader_preserves_changed_record_revision(
    clean_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """Changed forecast values create a new current revision."""

    original_payload = (FIXTURE_ROOT / "forecasts_sample.csv").read_bytes()
    revised_payload = (FIXTURE_ROOT / "forecasts_revised.csv").read_bytes()
    original_records = parse_weather_forecasts(original_payload, source_name="weather-forecasts")
    revised_records = parse_weather_forecasts(revised_payload, source_name="weather-forecasts")
    superseded_at = datetime(2026, 7, 8, 12, tzinfo=UTC)

    with clean_session_factory() as session:
        _persist_and_load_forecasts(session, tmp_path, original_payload, original_records)
        result = _persist_and_load_forecasts(
            session,
            tmp_path,
            revised_payload,
            revised_records,
            superseded_at_utc=superseded_at,
        )
        session.commit()
        rows = session.scalars(select(WeatherForecast).order_by(WeatherForecast.id)).all()
        revised_key_rows = [row for row in rows if row.variable_name == "temperature_c"]

    assert result.records_inserted == 1
    assert result.records_unchanged == 1
    assert result.records_superseded == 1
    assert len(rows) == 3
    assert [row.is_current for row in revised_key_rows] == [False, True]
    assert revised_key_rows[0].superseded_at_utc == superseded_at
    assert revised_key_rows[0].variable_value == Decimal("-5.200")
    assert revised_key_rows[1].variable_value == Decimal("-4.800")


def _persist_and_load_observations(
    session: Session,
    raw_root: Path,
    payload: bytes,
    records: list[ParsedWeatherObservationRecord],
    *,
    superseded_at_utc: datetime | None = None,
) -> WeatherObservationLoadResult:
    source = get_source_definition("weather-observations")
    ingestion_run = start_ingestion_run(session, source=source, mode="fixture")
    snapshot = persist_raw_snapshot(
        session,
        store=RawSnapshotStore(raw_root),
        source=source,
        ingestion_run=ingestion_run,
        payload=payload,
        metadata=RawSnapshotMetadata(
            retrieval_identifier="fixture://weather/observations.csv",
            source_url=None,
            retrieved_at_utc=datetime(2026, 7, 8, 12, tzinfo=UTC),
        ),
    ).snapshot

    return load_weather_observations(
        session,
        records=records,
        ingestion_run=ingestion_run,
        raw_snapshot=snapshot,
        superseded_at_utc=superseded_at_utc,
    )


def _persist_and_load_forecasts(
    session: Session,
    raw_root: Path,
    payload: bytes,
    records: list[ParsedWeatherForecastRecord],
    *,
    superseded_at_utc: datetime | None = None,
) -> WeatherForecastLoadResult:
    source = get_source_definition("weather-forecasts")
    ingestion_run = start_ingestion_run(session, source=source, mode="fixture")
    snapshot = persist_raw_snapshot(
        session,
        store=RawSnapshotStore(raw_root),
        source=source,
        ingestion_run=ingestion_run,
        payload=payload,
        metadata=RawSnapshotMetadata(
            retrieval_identifier="fixture://weather/forecasts.csv",
            source_url=None,
            retrieved_at_utc=datetime(2026, 7, 8, 12, tzinfo=UTC),
        ),
    ).snapshot

    return load_weather_forecasts(
        session,
        records=records,
        ingestion_run=ingestion_run,
        raw_snapshot=snapshot,
        superseded_at_utc=superseded_at_utc,
    )
