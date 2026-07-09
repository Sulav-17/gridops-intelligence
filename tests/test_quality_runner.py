"""Tests for the simple M03 quality runner."""

from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from gridops.config import Settings
from gridops.database import Base, make_engine, make_session_factory
from gridops.models import (
    IesoHourlyDemand,
    IngestionRun,
    QualityResult,
    QualityRun,
    RawSnapshot,
    WeatherForecast,
)
from gridops.quality.runner import main, run_quality_checks
from gridops.time_utils import TORONTO_TIME_ZONE, ieso_hour_ending_to_utc

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
def clean_session_factory(
    live_postgres_engine: Engine,
) -> Generator[sessionmaker[Session], None, None]:
    """Create a clean schema for quality runner tests."""

    Base.metadata.drop_all(live_postgres_engine)
    Base.metadata.create_all(live_postgres_engine)

    try:
        yield make_session_factory(live_postgres_engine)
    finally:
        Base.metadata.drop_all(live_postgres_engine)


@pytest.mark.integration
def test_quality_runner_persists_ieso_results_and_blocking_failures(
    clean_session_factory: sessionmaker[Session],
) -> None:
    """IESO runner executions persist results and surface blocking failures."""

    with clean_session_factory() as session:
        ingestion_run = _persist_ingestion_run(session, source_name="ieso-hourly-demand")
        snapshot = _persist_raw_snapshot(
            session,
            ingestion_run=ingestion_run,
            source_name="ieso-hourly-demand",
            source_type="electricity_demand",
        )
        _persist_ieso_row(
            session,
            ingestion_run=ingestion_run,
            snapshot=snapshot,
            service_date=date(2026, 1, 15),
            hour_ending=1,
        )
        _persist_ieso_row(
            session,
            ingestion_run=ingestion_run,
            snapshot=snapshot,
            service_date=date(2026, 1, 15),
            hour_ending=3,
        )
        session.commit()

    result = run_quality_checks(
        dataset_name="ieso_hourly_demand",
        checked_window_start_utc=datetime(2026, 1, 15, 5, tzinfo=UTC),
        checked_window_end_utc=datetime(2026, 1, 15, 8, tzinfo=UTC),
        now_utc=datetime(2026, 1, 15, 9, tzinfo=UTC),
        settings=Settings(database_url=SecretStr(TEST_DATABASE_URL)),
    )

    with clean_session_factory() as session:
        persisted_run = session.get_one(QualityRun, result.quality_run_id)
        persisted_results = list(
            session.scalars(
                select(QualityResult)
                .where(QualityResult.quality_run_id == result.quality_run_id)
                .order_by(QualityResult.id)
            ).all()
        )

    assert result.status == "succeeded"
    assert result.is_blocked is True
    assert result.blocking_result_count >= 1
    assert persisted_run.status == "succeeded"
    assert any(
        stored.check_name == "ieso_utc_interval_continuity" and stored.status == "failed"
        for stored in persisted_results
    )


@pytest.mark.integration
def test_quality_runner_persists_honest_no_data_result(
    clean_session_factory: sessionmaker[Session],
) -> None:
    """Datasets with no rows persist a safe failure instead of crashing."""

    result = run_quality_checks(
        dataset_name="weather_observations",
        now_utc=datetime(2026, 7, 9, 12, tzinfo=UTC),
        settings=Settings(database_url=SecretStr(TEST_DATABASE_URL)),
    )

    with clean_session_factory() as session:
        persisted_results = list(
            session.scalars(
                select(QualityResult)
                .where(QualityResult.quality_run_id == result.quality_run_id)
                .order_by(QualityResult.id)
            ).all()
        )

    assert result.status == "succeeded"
    assert result.is_blocked is True
    assert len(persisted_results) == 1
    assert persisted_results[0].check_name == "dataset_rows_present"
    assert persisted_results[0].severity == "critical"
    assert "weather_observations" in (persisted_results[0].safe_detail or "")


@pytest.mark.integration
def test_quality_runner_persists_weather_forecast_group_results(
    clean_session_factory: sessionmaker[Session],
) -> None:
    """Forecast runner executions persist completeness for current issue groups."""

    with clean_session_factory() as session:
        ingestion_run = _persist_ingestion_run(session, source_name="weather-forecasts")
        snapshot = _persist_raw_snapshot(
            session,
            ingestion_run=ingestion_run,
            source_name="weather-forecasts",
            source_type="weather_forecast",
        )
        _persist_weather_forecast(
            session,
            ingestion_run=ingestion_run,
            snapshot=snapshot,
            issue_time_utc=datetime(2026, 1, 15, 0, tzinfo=UTC),
            valid_time_utc=datetime(2026, 1, 15, 6, tzinfo=UTC),
            lead_time_hours=6,
        )
        _persist_weather_forecast(
            session,
            ingestion_run=ingestion_run,
            snapshot=snapshot,
            issue_time_utc=datetime(2026, 1, 15, 0, tzinfo=UTC),
            valid_time_utc=datetime(2026, 1, 15, 7, tzinfo=UTC),
            lead_time_hours=7,
        )
        session.commit()

    result = run_quality_checks(
        dataset_name="weather_forecasts",
        now_utc=datetime(2026, 1, 15, 12, tzinfo=UTC),
        settings=Settings(database_url=SecretStr(TEST_DATABASE_URL)),
    )

    with clean_session_factory() as session:
        persisted_results = list(
            session.scalars(
                select(QualityResult)
                .where(QualityResult.quality_run_id == result.quality_run_id)
                .order_by(QualityResult.id)
            ).all()
        )

    assert result.status == "succeeded"
    assert any(
        stored.check_name == "weather_forecast_valid_time_completeness"
        and stored.status == "passed"
        for stored in persisted_results
    )


@pytest.mark.integration
def test_quality_runner_persists_raw_snapshot_metadata_results(
    clean_session_factory: sessionmaker[Session],
) -> None:
    """Raw snapshot runner executions persist the source metadata result."""

    with clean_session_factory() as session:
        ingestion_run = _persist_ingestion_run(session, source_name="weather-observations")
        _persist_raw_snapshot(
            session,
            ingestion_run=ingestion_run,
            source_name="weather-observations",
            source_type="weather_observation",
        )
        session.commit()

    result = run_quality_checks(
        dataset_name="raw_snapshots",
        now_utc=datetime(2026, 7, 9, 12, tzinfo=UTC),
        settings=Settings(database_url=SecretStr(TEST_DATABASE_URL)),
    )

    with clean_session_factory() as session:
        stored = session.scalar(
            select(QualityResult).where(QualityResult.quality_run_id == result.quality_run_id)
        )

    assert result.status == "succeeded"
    assert result.is_blocked is False
    assert stored is not None
    assert stored.check_name == "raw_snapshot_metadata"
    assert stored.status == "passed"


@pytest.mark.integration
def test_quality_runner_persists_ingestion_run_metadata_results(
    clean_session_factory: sessionmaker[Session],
) -> None:
    """Ingestion run runner executions persist the metadata result."""

    with clean_session_factory() as session:
        _persist_ingestion_run(session, source_name="weather-observations")
        session.commit()

    result = run_quality_checks(
        dataset_name="ingestion_runs",
        now_utc=datetime(2026, 7, 9, 12, tzinfo=UTC),
        settings=Settings(database_url=SecretStr(TEST_DATABASE_URL)),
    )

    with clean_session_factory() as session:
        stored = session.scalar(
            select(QualityResult).where(QualityResult.quality_run_id == result.quality_run_id)
        )

    assert result.status == "succeeded"
    assert result.is_blocked is False
    assert stored is not None
    assert stored.check_name == "ingestion_run_metadata"
    assert stored.status == "passed"


def test_quality_runner_main_rejects_naive_now_utc() -> None:
    """CLI timestamp arguments must be timezone-aware."""

    with pytest.raises(SystemExit):
        main(["--dataset", "ieso_hourly_demand", "--now-utc", "2026-07-09T12:00:00"])


def _persist_ingestion_run(session: Session, *, source_name: str) -> IngestionRun:
    run = IngestionRun(
        source_name=source_name,
        source_type="fixture",
        mode="fixture",
        parser_version="test:v1",
        status="succeeded",
        started_at_utc=datetime(2026, 7, 9, 12, tzinfo=UTC),
        finished_at_utc=datetime(2026, 7, 9, 12, 1, tzinfo=UTC),
        records_seen=2,
        records_loaded=2,
    )
    session.add(run)
    session.flush()
    return run


def _persist_raw_snapshot(
    session: Session,
    *,
    ingestion_run: IngestionRun,
    source_name: str,
    source_type: str,
) -> RawSnapshot:
    snapshot = RawSnapshot(
        source_name=source_name,
        source_type=source_type,
        retrieval_identifier=f"fixture://{source_name}.csv",
        source_url=None,
        retrieved_at_utc=datetime(2026, 7, 9, 12, tzinfo=UTC),
        published_at_utc=None,
        content_hash_sha256=(source_name[:1] * 64)[:64],
        content_type="text/csv",
        parser_version="test:v1",
        storage_path=f"{source_name}/sample.csv",
        byte_size=100,
        ingestion_run_id=ingestion_run.id,
    )
    session.add(snapshot)
    session.flush()
    return snapshot


def _persist_ieso_row(
    session: Session,
    *,
    ingestion_run: IngestionRun,
    snapshot: RawSnapshot,
    service_date: date,
    hour_ending: int,
) -> None:
    service_midnight = datetime(
        service_date.year,
        service_date.month,
        service_date.day,
        tzinfo=TORONTO_TIME_ZONE,
    )
    interval_end_utc = ieso_hour_ending_to_utc(service_midnight, hour_ending)
    session.add(
        IesoHourlyDemand(
            source_service_date=service_date,
            source_hour_ending=hour_ending,
            interval_start_utc=interval_end_utc - timedelta(hours=1),
            interval_end_utc=interval_end_utc,
            demand_mw=Decimal("18000"),
            source_snapshot_id=snapshot.id,
            ingestion_run_id=ingestion_run.id,
            row_hash_sha256=f"{hour_ending:064d}"[-64:],
            is_current=True,
        )
    )


def _persist_weather_forecast(
    session: Session,
    *,
    ingestion_run: IngestionRun,
    snapshot: RawSnapshot,
    issue_time_utc: datetime,
    valid_time_utc: datetime,
    lead_time_hours: int,
) -> None:
    session.add(
        WeatherForecast(
            source_name="weather-forecasts",
            forecast_location="TORONTO",
            source_native_issue_time=issue_time_utc.isoformat(),
            source_native_valid_time=valid_time_utc.isoformat(),
            issue_time_utc=issue_time_utc,
            valid_time_utc=valid_time_utc,
            lead_time_hours=lead_time_hours,
            variable_name="temperature_c",
            variable_value=Decimal("5"),
            variable_unit="C",
            source_snapshot_id=snapshot.id,
            ingestion_run_id=ingestion_run.id,
            row_hash_sha256=f"{lead_time_hours:064d}"[-64:],
            is_current=True,
        )
    )
