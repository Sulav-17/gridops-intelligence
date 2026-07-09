"""Tests for M02 ingestion storage foundation."""

from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy import inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from gridops.config import Settings
from gridops.database import Base, make_engine, make_session_factory
from gridops.ingestion.raw_store import RawSnapshotMetadata, RawSnapshotStore, persist_raw_snapshot
from gridops.ingestion.runs import (
    mark_ingestion_run_failed,
    mark_ingestion_run_succeeded,
    start_ingestion_run,
)
from gridops.models import IngestionRun, RawSnapshot
from gridops.sources import get_source_definition

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
    """Create a clean M02 schema for integration tests."""

    Base.metadata.drop_all(live_postgres_engine)
    Base.metadata.create_all(live_postgres_engine)

    try:
        yield make_session_factory(live_postgres_engine)
    finally:
        Base.metadata.drop_all(live_postgres_engine)


def test_raw_snapshot_store_writes_payload_once(tmp_path: Path) -> None:
    """Raw payload files are stored by source and content hash."""

    payload = b"hour, demand\n1, 100\n"
    store = RawSnapshotStore(tmp_path)

    first_path = store.write_payload(source_name="ieso-hourly-demand", payload=payload)
    second_path = store.write_payload(source_name="ieso-hourly-demand", payload=payload)

    assert first_path == second_path
    assert (tmp_path / first_path).read_bytes() == payload
    assert len(list((tmp_path / "ieso-hourly-demand").iterdir())) == 1


@pytest.mark.integration
def test_ingestion_run_success_and_failure_persist(
    clean_session_factory: sessionmaker[Session],
) -> None:
    """Ingestion run helpers persist bounded success and failure state."""

    source = get_source_definition("ieso-hourly-demand")
    started_at = datetime(2026, 7, 8, 12, tzinfo=UTC)
    finished_at = datetime(2026, 7, 8, 12, 5, tzinfo=UTC)

    with clean_session_factory() as session:
        success = start_ingestion_run(
            session,
            source=source,
            mode="fixture",
            started_at_utc=started_at,
        )
        mark_ingestion_run_succeeded(
            success,
            records_seen=24,
            records_loaded=24,
            finished_at_utc=finished_at,
        )

        failure = start_ingestion_run(session, source=source, mode="fixture")
        mark_ingestion_run_failed(
            failure,
            RuntimeError(
                "failed password=secret postgresql://user:password@localhost/gridops_test"
            ),
            finished_at_utc=finished_at,
        )
        session.commit()

        persisted = session.scalars(select(IngestionRun).order_by(IngestionRun.id)).all()

    assert [run.status for run in persisted] == ["succeeded", "failed"]
    assert persisted[0].records_seen == 24
    assert persisted[0].records_loaded == 24
    assert persisted[1].error_type == "RuntimeError"
    assert persisted[1].error_message is not None
    assert "secret" not in persisted[1].error_message
    assert "password@localhost" not in persisted[1].error_message


@pytest.mark.integration
def test_raw_snapshot_metadata_persistence_and_dedupe(
    clean_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """Identical raw payloads do not create duplicate snapshots for a source."""

    source = get_source_definition("ieso-hourly-demand")
    payload = b"date,hour_ending,demand_mw\n2026-01-01,1,18000\n"
    metadata = RawSnapshotMetadata(
        retrieval_identifier="fixture://ieso/hourly_demand.csv",
        source_url=None,
        retrieved_at_utc=datetime(2026, 7, 8, 12, tzinfo=UTC),
        published_at_utc=datetime(2026, 7, 8, 11, tzinfo=UTC),
    )
    store = RawSnapshotStore(tmp_path)

    with clean_session_factory() as session:
        first_run = start_ingestion_run(session, source=source, mode="fixture")
        first_result = persist_raw_snapshot(
            session,
            store=store,
            source=source,
            ingestion_run=first_run,
            payload=payload,
            metadata=metadata,
        )
        second_run = start_ingestion_run(session, source=source, mode="fixture")
        second_result = persist_raw_snapshot(
            session,
            store=store,
            source=source,
            ingestion_run=second_run,
            payload=payload,
            metadata=metadata,
        )
        session.commit()

        snapshots = session.scalars(select(RawSnapshot)).all()

    assert first_result.created is True
    assert second_result.created is False
    assert first_result.snapshot.id == second_result.snapshot.id
    assert len(snapshots) == 1
    assert snapshots[0].source_name == "ieso-hourly-demand"
    assert snapshots[0].source_type == "electricity_demand"
    assert snapshots[0].retrieval_identifier == "fixture://ieso/hourly_demand.csv"
    assert snapshots[0].published_at_utc == datetime(2026, 7, 8, 11, tzinfo=UTC)
    assert snapshots[0].byte_size == len(payload)
    assert len(snapshots[0].content_hash_sha256) == 64
    assert (tmp_path / snapshots[0].storage_path).read_bytes() == payload


@pytest.mark.integration
def test_m02_migration_creates_expected_tables(
    live_postgres_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Alembic can upgrade a clean database to the M02 schema."""

    Base.metadata.drop_all(live_postgres_engine)
    with live_postgres_engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")

    monkeypatch.setenv("GRIDOPS_DATABASE_URL", TEST_DATABASE_URL)
    command.upgrade(Config("alembic.ini"), "head")

    inspector = inspect(live_postgres_engine)
    table_names = set(inspector.get_table_names())

    assert {
        "ingestion_runs",
        "raw_snapshots",
        "ieso_hourly_demand",
        "weather_observations",
        "weather_forecasts",
    }.issubset(table_names)
