"""Tests for the simple M02 fixture ingestion runner."""

from collections.abc import Generator
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from gridops.config import Settings
from gridops.database import Base, make_engine, make_session_factory
from gridops.ingestion.runner import main, run_fixture_ingestion
from gridops.models import IesoHourlyDemand, IngestionRun, RawSnapshot

TEST_DATABASE_URL = "postgresql+psycopg://gridops:gridops@localhost:55432/gridops_test"
FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "ingestion"


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
    """Create a clean M02 schema for runner tests."""

    Base.metadata.drop_all(live_postgres_engine)
    Base.metadata.create_all(live_postgres_engine)

    try:
        yield make_session_factory(live_postgres_engine)
    finally:
        Base.metadata.drop_all(live_postgres_engine)


@pytest.mark.integration
def test_fixture_runner_loads_ieso_demand(
    clean_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """The runner coordinates raw snapshot, parse, load, and success status."""

    settings = Settings(database_url=SecretStr(TEST_DATABASE_URL))
    result = run_fixture_ingestion(
        source_name="ieso-demand",
        fixture_path=FIXTURE_ROOT / "ieso" / "hourly_demand_sample.csv",
        raw_root=tmp_path,
        settings=settings,
    )

    with clean_session_factory() as session:
        run = session.get_one(IngestionRun, result.ingestion_run_id)
        demand_count = session.scalar(select(func.count()).select_from(IesoHourlyDemand))
        snapshot_count = session.scalar(select(func.count()).select_from(RawSnapshot))

    assert result.status == "succeeded"
    assert result.records_seen == 3
    assert result.records_loaded == 3
    assert run.status == "succeeded"
    assert run.records_seen == 3
    assert run.records_loaded == 3
    assert demand_count == 3
    assert snapshot_count == 1


@pytest.mark.integration
def test_fixture_runner_records_parse_failure_safely(
    clean_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """A failed parse leaves a failed ingestion run with safe details."""

    settings = Settings(database_url=SecretStr(TEST_DATABASE_URL))
    result = run_fixture_ingestion(
        source_name="ieso-demand",
        fixture_path=FIXTURE_ROOT / "ieso" / "hourly_demand_invalid.csv",
        raw_root=tmp_path,
        settings=settings,
    )

    with clean_session_factory() as session:
        run = session.get_one(IngestionRun, result.ingestion_run_id)
        demand_count = session.scalar(select(func.count()).select_from(IesoHourlyDemand))

    assert result.status == "failed"
    assert run.status == "failed"
    assert run.error_type == "ValueError"
    assert run.error_message is not None
    assert "missing columns" in run.error_message
    assert demand_count == 0


def test_runner_main_rejects_non_fixture_mode() -> None:
    """The CLI only exposes fixture mode in M02."""

    with pytest.raises(SystemExit):
        main(
            [
                "--source",
                "ieso-demand",
                "--mode",
                "live",
                "--path",
                "unused.csv",
            ]
        )
