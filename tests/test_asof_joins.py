"""Tests for point-in-time weather as-of joins."""

from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import SecretStr
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from gridops.config import Settings
from gridops.database import Base, make_engine, make_session_factory
from gridops.forecasting.asof import (
    select_archived_weather_forecasts_asof,
    select_latest_weather_observations_asof,
)
from gridops.models import IngestionRun, RawSnapshot, WeatherForecast, WeatherObservation

TEST_DATABASE_URL = "postgresql+psycopg://gridops:gridops@localhost:55432/gridops_test"


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
def clean_engine(live_postgres_engine: Engine) -> Generator[Engine, None, None]:
    """Create a clean schema for as-of join tests."""

    Base.metadata.drop_all(live_postgres_engine)
    Base.metadata.create_all(live_postgres_engine)

    try:
        yield live_postgres_engine
    finally:
        Base.metadata.drop_all(live_postgres_engine)


@pytest.mark.integration
def test_weather_observation_asof_ignores_observations_after_issue_time(
    clean_engine: Engine,
) -> None:
    """Observation features only use observations known at issue time."""

    session_factory = make_session_factory(clean_engine)
    issue_time = datetime(2026, 7, 9, 15, tzinfo=UTC)

    with session_factory() as session:
        run, snapshot = _persist_evidence(session)
        past = _weather_observation(
            snapshot=snapshot,
            ingestion_run=run,
            station_id="toronto",
            observed_at_utc=datetime(2026, 7, 9, 14, tzinfo=UTC),
            temperature_c=Decimal("21.0"),
        )
        future = _weather_observation(
            snapshot=snapshot,
            ingestion_run=run,
            station_id="toronto",
            observed_at_utc=datetime(2026, 7, 9, 16, tzinfo=UTC),
            temperature_c=Decimal("99.0"),
        )
        session.add_all([past, future])
        session.commit()

        selected = select_latest_weather_observations_asof(
            session,
            forecast_issue_time_utc=issue_time,
        )

    assert selected["toronto"].observed_at_utc == datetime(2026, 7, 9, 14, tzinfo=UTC)
    assert selected["toronto"].temperature_c == Decimal("21.000")


@pytest.mark.integration
def test_archived_weather_forecast_asof_selects_latest_issue_at_or_before_issue_time(
    clean_engine: Engine,
) -> None:
    """Archived forecasts are selected by latest allowed issue time per target key."""

    session_factory = make_session_factory(clean_engine)
    issue_time = datetime(2026, 7, 9, 15, tzinfo=UTC)
    valid_time = datetime(2026, 7, 9, 16, tzinfo=UTC)

    with session_factory() as session:
        run, snapshot = _persist_evidence(session)
        session.add_all(
            [
                _weather_forecast(
                    snapshot=snapshot,
                    ingestion_run=run,
                    issue_time_utc=datetime(2026, 7, 9, 12, tzinfo=UTC),
                    valid_time_utc=valid_time,
                    value=Decimal("19.0"),
                ),
                _weather_forecast(
                    snapshot=snapshot,
                    ingestion_run=run,
                    issue_time_utc=datetime(2026, 7, 9, 14, tzinfo=UTC),
                    valid_time_utc=valid_time,
                    value=Decimal("20.0"),
                ),
                _weather_forecast(
                    snapshot=snapshot,
                    ingestion_run=run,
                    issue_time_utc=datetime(2026, 7, 9, 16, tzinfo=UTC),
                    valid_time_utc=valid_time,
                    value=Decimal("99.0"),
                ),
            ]
        )
        session.commit()

        selected = select_archived_weather_forecasts_asof(
            session,
            forecast_issue_time_utc=issue_time,
            valid_times_utc=[valid_time],
        )

    key = ("ontario", "temperature_c", valid_time)
    assert selected[key].issue_time_utc == datetime(2026, 7, 9, 14, tzinfo=UTC)
    assert selected[key].variable_value == Decimal("20.000")


@pytest.mark.integration
def test_archived_weather_forecast_asof_rejects_future_only_issue_times(
    clean_engine: Engine,
) -> None:
    """No forecast is selected when only future forecast issues exist."""

    session_factory = make_session_factory(clean_engine)
    issue_time = datetime(2026, 7, 9, 15, tzinfo=UTC)
    valid_time = datetime(2026, 7, 9, 16, tzinfo=UTC)

    with session_factory() as session:
        run, snapshot = _persist_evidence(session)
        session.add(
            _weather_forecast(
                snapshot=snapshot,
                ingestion_run=run,
                issue_time_utc=datetime(2026, 7, 9, 16, tzinfo=UTC),
                valid_time_utc=valid_time,
                value=Decimal("99.0"),
            )
        )
        session.commit()

        selected = select_archived_weather_forecasts_asof(
            session,
            forecast_issue_time_utc=issue_time,
            valid_times_utc=[valid_time],
        )

    assert selected == {}


def _persist_evidence(session: Session) -> tuple[IngestionRun, RawSnapshot]:
    run = IngestionRun(
        source_name="fixture-source",
        source_type="fixture",
        mode="fixture",
        parser_version="test",
        status="succeeded",
        started_at_utc=datetime(2026, 7, 9, 12, tzinfo=UTC),
        finished_at_utc=datetime(2026, 7, 9, 12, 1, tzinfo=UTC),
        records_seen=1,
        records_loaded=1,
    )
    snapshot = RawSnapshot(
        source_name="fixture-source",
        source_type="fixture",
        retrieval_identifier="fixture://weather",
        source_url=None,
        retrieved_at_utc=datetime(2026, 7, 9, 12, tzinfo=UTC),
        published_at_utc=None,
        content_hash_sha256="b" * 64,
        content_type="text/csv",
        parser_version="test",
        storage_path="fixture/weather.csv",
        byte_size=10,
        ingestion_run=run,
    )
    session.add_all([run, snapshot])
    session.flush()

    return run, snapshot


def _weather_observation(
    *,
    snapshot: RawSnapshot,
    ingestion_run: IngestionRun,
    station_id: str,
    observed_at_utc: datetime,
    temperature_c: Decimal,
) -> WeatherObservation:
    return WeatherObservation(
        source_name="fixture-weather",
        source_station_id=station_id,
        source_native_timestamp=observed_at_utc.isoformat(),
        observed_at_utc=observed_at_utc,
        temperature_c=temperature_c,
        relative_humidity_percent=Decimal("50.0"),
        wind_speed_kph=Decimal("10.0"),
        precipitation_mm=Decimal("0.0"),
        source_snapshot_id=snapshot.id,
        ingestion_run_id=ingestion_run.id,
        row_hash_sha256=f"{station_id}{observed_at_utc.isoformat()}".encode()
        .hex()[:64]
        .ljust(
            64,
            "0",
        ),
        is_current=True,
        superseded_at_utc=None,
    )


def _weather_forecast(
    *,
    snapshot: RawSnapshot,
    ingestion_run: IngestionRun,
    issue_time_utc: datetime,
    valid_time_utc: datetime,
    value: Decimal,
) -> WeatherForecast:
    return WeatherForecast(
        source_name="fixture-weather",
        forecast_location="ontario",
        source_native_issue_time=issue_time_utc.isoformat(),
        source_native_valid_time=valid_time_utc.isoformat(),
        issue_time_utc=issue_time_utc,
        valid_time_utc=valid_time_utc,
        lead_time_hours=int((valid_time_utc - issue_time_utc).total_seconds() // 3600),
        variable_name="temperature_c",
        variable_value=value,
        variable_unit="C",
        source_snapshot_id=snapshot.id,
        ingestion_run_id=ingestion_run.id,
        row_hash_sha256=f"{issue_time_utc.isoformat()}{value}".encode().hex()[:64].ljust(64, "0"),
        is_current=True,
        superseded_at_utc=None,
    )
