"""Tests for fixture-backed IESO hourly demand ingestion."""

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
from gridops.ingestion.loaders.ieso_demand import IesoDemandLoadResult, load_ieso_hourly_demand
from gridops.ingestion.parsers.ieso_demand import (
    ParsedIesoDemandRecord,
    parse_ieso_hourly_demand,
)
from gridops.ingestion.raw_store import RawSnapshotMetadata, RawSnapshotStore, persist_raw_snapshot
from gridops.ingestion.runs import start_ingestion_run
from gridops.models import IesoHourlyDemand
from gridops.sources import get_source_definition

TEST_DATABASE_URL = "postgresql+psycopg://gridops:gridops@localhost:55432/gridops_test"
FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "ingestion" / "ieso"


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
    """Create a clean M02 schema for IESO loader tests."""

    Base.metadata.drop_all(live_postgres_engine)
    Base.metadata.create_all(live_postgres_engine)

    try:
        yield make_session_factory(live_postgres_engine)
    finally:
        Base.metadata.drop_all(live_postgres_engine)


def test_ieso_demand_parser_preserves_source_fields_and_values() -> None:
    """The parser preserves source-native date and hour-ending values."""

    payload = (FIXTURE_ROOT / "hourly_demand_sample.csv").read_bytes()

    records = parse_ieso_hourly_demand(payload)

    assert len(records) == 3
    assert records[0].source_service_date == "2026-01-15"
    assert records[0].source_hour_ending == 1
    assert records[0].demand_mw == Decimal("18000.5")
    assert len(records[0].row_hash_sha256) == 64


def test_ieso_demand_parser_uses_hour_ending_time_contract() -> None:
    """Hour-ending is interpreted as an IESO local endpoint, not a zero-based hour."""

    payload = (FIXTURE_ROOT / "hourly_demand_sample.csv").read_bytes()

    records = parse_ieso_hourly_demand(payload)

    assert records[0].interval_start_utc == datetime(2026, 1, 15, 5, tzinfo=UTC)
    assert records[0].interval_end_utc == datetime(2026, 1, 15, 6, tzinfo=UTC)
    assert records[2].source_hour_ending == 24
    assert records[2].interval_end_utc == datetime(2026, 1, 16, 5, tzinfo=UTC)


@pytest.mark.integration
def test_ieso_demand_loader_is_idempotent(
    clean_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """Loading the same fixture twice does not duplicate silver records."""

    payload = (FIXTURE_ROOT / "hourly_demand_sample.csv").read_bytes()
    records = parse_ieso_hourly_demand(payload)

    with clean_session_factory() as session:
        first_result = _persist_and_load(session, tmp_path, payload, records)
        second_result = _persist_and_load(session, tmp_path, payload, records)
        session.commit()

        rows = session.scalars(select(IesoHourlyDemand)).all()

    assert first_result.records_seen == 3
    assert first_result.records_inserted == 3
    assert first_result.records_unchanged == 0
    assert second_result.records_seen == 3
    assert second_result.records_inserted == 0
    assert second_result.records_unchanged == 3
    assert len(rows) == 3
    assert all(row.is_current for row in rows)


@pytest.mark.integration
def test_ieso_demand_loader_preserves_changed_record_revision(
    clean_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """Changed demand for the same source key creates revision evidence."""

    original_payload = (FIXTURE_ROOT / "hourly_demand_sample.csv").read_bytes()
    revised_payload = (FIXTURE_ROOT / "hourly_demand_revised.csv").read_bytes()
    original_records = parse_ieso_hourly_demand(original_payload)
    revised_records = parse_ieso_hourly_demand(revised_payload)
    superseded_at = datetime(2026, 7, 8, 12, tzinfo=UTC)

    with clean_session_factory() as session:
        _persist_and_load(session, tmp_path, original_payload, original_records)
        revised_result = _persist_and_load(
            session,
            tmp_path,
            revised_payload,
            revised_records,
            superseded_at_utc=superseded_at,
        )
        session.commit()

        rows = session.scalars(
            select(IesoHourlyDemand).order_by(
                IesoHourlyDemand.source_hour_ending,
                IesoHourlyDemand.id,
            )
        ).all()
        hour_two_rows = [row for row in rows if row.source_hour_ending == 2]

    assert revised_result.records_seen == 3
    assert revised_result.records_inserted == 1
    assert revised_result.records_unchanged == 2
    assert revised_result.records_superseded == 1
    assert len(rows) == 4
    assert len(hour_two_rows) == 2
    assert [row.is_current for row in hour_two_rows] == [False, True]
    assert hour_two_rows[0].superseded_at_utc == superseded_at
    assert hour_two_rows[0].demand_mw == Decimal("17750.000")
    assert hour_two_rows[1].demand_mw == Decimal("17825.000")


def _persist_and_load(
    session: Session,
    raw_root: Path,
    payload: bytes,
    records: list[ParsedIesoDemandRecord],
    *,
    superseded_at_utc: datetime | None = None,
) -> IesoDemandLoadResult:
    source = get_source_definition("ieso-hourly-demand")
    ingestion_run = start_ingestion_run(session, source=source, mode="fixture")
    snapshot_result = persist_raw_snapshot(
        session,
        store=RawSnapshotStore(raw_root),
        source=source,
        ingestion_run=ingestion_run,
        payload=payload,
        metadata=RawSnapshotMetadata(
            retrieval_identifier="fixture://ieso/hourly_demand.csv",
            source_url=None,
            retrieved_at_utc=datetime(2026, 7, 8, 12, tzinfo=UTC),
        ),
    )

    return load_ieso_hourly_demand(
        session,
        records=records,
        ingestion_run=ingestion_run,
        raw_snapshot=snapshot_result.snapshot,
        superseded_at_utc=superseded_at_utc,
    )
