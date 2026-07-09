"""Tests for M03 quality persistence helpers."""

from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from alembic import command
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy import inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from gridops.config import Settings
from gridops.database import Base, make_engine, make_session_factory
from gridops.ingestion.runs import start_ingestion_run
from gridops.models import IngestionRun, QualityResult, QualityRun, RawSnapshot
from gridops.quality.contracts import (
    QualityCheckCategory,
    QualityResultStatus,
    QualityRunStatus,
    QualitySeverity,
)
from gridops.quality.results import (
    mark_quality_run_failed,
    mark_quality_run_succeeded,
    start_quality_run,
    store_quality_result,
)
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
    """Create a clean schema for quality persistence tests."""

    Base.metadata.drop_all(live_postgres_engine)
    Base.metadata.create_all(live_postgres_engine)

    try:
        yield make_session_factory(live_postgres_engine)
    finally:
        Base.metadata.drop_all(live_postgres_engine)


@pytest.mark.integration
def test_quality_run_persistence(clean_session_factory: sessionmaker[Session]) -> None:
    """Quality run helpers persist lifecycle state and checked windows."""

    started_at = datetime(2026, 7, 9, 12, tzinfo=UTC)
    completed_at = datetime(2026, 7, 9, 12, 5, tzinfo=UTC)
    window_start = datetime(2026, 1, 1, tzinfo=UTC)
    window_end = datetime(2026, 1, 2, tzinfo=UTC)

    with clean_session_factory() as session:
        run = start_quality_run(
            session,
            dataset_name="ieso_hourly_demand",
            started_at_utc=started_at,
            checked_window_start_utc=window_start,
            checked_window_end_utc=window_end,
        )
        mark_quality_run_succeeded(run, completed_at_utc=completed_at)
        session.commit()

        persisted = session.scalar(select(QualityRun))

    assert persisted is not None
    assert persisted.dataset_name == "ieso_hourly_demand"
    assert persisted.status == QualityRunStatus.SUCCEEDED.value
    assert persisted.started_at_utc == started_at
    assert persisted.completed_at_utc == completed_at
    assert persisted.checked_window_start_utc == window_start
    assert persisted.checked_window_end_utc == window_end


@pytest.mark.integration
def test_quality_result_persistence_links_existing_evidence(
    clean_session_factory: sessionmaker[Session],
) -> None:
    """Quality results can reference existing ingestion runs and raw snapshots."""

    created_at = datetime(2026, 7, 9, 13, tzinfo=UTC)

    with clean_session_factory() as session:
        ingestion_run, snapshot = _persist_source_evidence(session)
        quality_run = start_quality_run(session, dataset_name="raw_snapshots")

        result = store_quality_result(
            session,
            quality_run=quality_run,
            check_name="raw_snapshot_content_hash_present",
            check_category=QualityCheckCategory.SOURCE_METADATA,
            severity=QualitySeverity.ERROR,
            status=QualityResultStatus.FAILED,
            observed_value="missing",
            expected_value="sha256 hex digest",
            affected_record_count=1,
            safe_detail="password=secret postgresql://user:password@localhost/gridops",
            is_blocking=True,
            related_ingestion_run_id=ingestion_run.id,
            related_raw_snapshot_id=snapshot.id,
            created_at_utc=created_at,
        )
        mark_quality_run_failed(quality_run, "token=abc123", completed_at_utc=created_at)
        session.commit()

        persisted_result = session.scalar(
            select(QualityResult).where(QualityResult.id == result.id)
        )
        persisted_run = session.scalar(select(QualityRun).where(QualityRun.id == quality_run.id))

    assert persisted_result is not None
    assert persisted_run is not None
    assert persisted_result.dataset_name == "raw_snapshots"
    assert persisted_result.check_category == QualityCheckCategory.SOURCE_METADATA.value
    assert persisted_result.severity == QualitySeverity.ERROR.value
    assert persisted_result.status == QualityResultStatus.FAILED.value
    assert persisted_result.observed_value == "missing"
    assert persisted_result.expected_value == "sha256 hex digest"
    assert persisted_result.affected_record_count == 1
    assert persisted_result.is_blocking is True
    assert persisted_result.related_ingestion_run_id == ingestion_run.id
    assert persisted_result.related_raw_snapshot_id == snapshot.id
    assert persisted_result.created_at_utc == created_at
    assert persisted_result.safe_detail is not None
    assert "secret" not in persisted_result.safe_detail
    assert "password@localhost" not in persisted_result.safe_detail
    assert persisted_run.status == QualityRunStatus.FAILED.value
    assert persisted_run.safe_error_detail == "token=[REDACTED]"


def test_quality_persistence_rejects_naive_timestamps() -> None:
    """Quality persistence helpers do not silently accept naive datetimes."""

    engine = make_engine(Settings(database_url=SecretStr(TEST_DATABASE_URL)))

    try:
        session_factory = make_session_factory(engine)
        with session_factory() as session, pytest.raises(ValueError, match="timezone-aware"):
            start_quality_run(
                session,
                dataset_name="ieso_hourly_demand",
                started_at_utc=datetime(2026, 7, 9, 12),
            )
    finally:
        engine.dispose()


def test_quality_result_rejects_negative_affected_record_count() -> None:
    """Affected record counts cannot be negative."""

    run = QualityRun(
        id=1,
        dataset_name="ieso_hourly_demand",
        status=QualityRunStatus.RUNNING.value,
        started_at_utc=datetime(2026, 7, 9, 12, tzinfo=UTC),
    )
    engine = make_engine(Settings(database_url=SecretStr(TEST_DATABASE_URL)))

    try:
        session_factory = make_session_factory(engine)
        with session_factory() as session, pytest.raises(ValueError, match="cannot be negative"):
            store_quality_result(
                session,
                quality_run=run,
                check_name="row_count",
                check_category=QualityCheckCategory.SCHEMA,
                severity=QualitySeverity.INFO,
                status=QualityResultStatus.PASSED,
                affected_record_count=-1,
            )
    finally:
        engine.dispose()


@pytest.mark.integration
def test_m03_migration_creates_quality_tables(
    live_postgres_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Alembic can upgrade a clean database to include M03 quality storage."""

    Base.metadata.drop_all(live_postgres_engine)
    with live_postgres_engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")

    monkeypatch.setenv("GRIDOPS_DATABASE_URL", TEST_DATABASE_URL)
    command.upgrade(Config("alembic.ini"), "head")

    inspector = inspect(live_postgres_engine)
    table_names = set(inspector.get_table_names())
    quality_result_columns = {column["name"] for column in inspector.get_columns("quality_results")}

    assert {"quality_runs", "quality_results"}.issubset(table_names)
    assert {
        "quality_run_id",
        "dataset_name",
        "check_name",
        "check_category",
        "severity",
        "status",
        "observed_value",
        "expected_value",
        "affected_record_count",
        "safe_detail",
        "is_blocking",
        "related_ingestion_run_id",
        "related_raw_snapshot_id",
        "created_at_utc",
    }.issubset(quality_result_columns)


def _persist_source_evidence(session: Session) -> tuple[IngestionRun, RawSnapshot]:
    source = get_source_definition("ieso-hourly-demand")
    ingestion_run = start_ingestion_run(
        session,
        source=source,
        mode="fixture",
        started_at_utc=datetime(2026, 7, 9, 12, tzinfo=UTC),
    )
    snapshot = RawSnapshot(
        source_name=source.name,
        source_type=source.source_type,
        retrieval_identifier="fixture://ieso/hourly_demand.csv",
        source_url=None,
        retrieved_at_utc=datetime(2026, 7, 9, 12, tzinfo=UTC),
        published_at_utc=None,
        content_hash_sha256="a" * 64,
        content_type=source.content_type,
        parser_version=source.parser_version,
        storage_path="ieso-hourly-demand/a.csv",
        byte_size=10,
        ingestion_run=ingestion_run,
    )
    session.add(snapshot)
    session.flush()

    return ingestion_run, snapshot
