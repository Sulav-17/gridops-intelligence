"""Tests for source-health summaries and API output."""

from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from gridops.api import create_app
from gridops.config import AppEnvironment, Settings
from gridops.database import Base, make_engine, make_session_factory
from gridops.models import QualityResult, QualityRun
from gridops.quality.contracts import DATASET_CONTRACTS
from gridops.quality.source_health import summarize_source_health

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
    """Create a clean schema for source-health tests."""

    Base.metadata.drop_all(live_postgres_engine)
    Base.metadata.create_all(live_postgres_engine)

    try:
        yield make_session_factory(live_postgres_engine)
    finally:
        Base.metadata.drop_all(live_postgres_engine)


@pytest.fixture
def api_settings() -> Settings:
    """Create API test settings."""

    return Settings(
        app_environment=AppEnvironment.TEST,
        database_url=SecretStr(TEST_DATABASE_URL),
    )


@pytest.mark.integration
def test_source_health_summary_uses_latest_persisted_run(
    clean_session_factory: sessionmaker[Session],
) -> None:
    """Source health reports latest run status, worst severity, counts, and safe details."""

    with clean_session_factory() as session:
        _seed_quality_run(
            session,
            dataset_name="ieso_hourly_demand",
            status="succeeded",
            completed_at_utc=datetime(2026, 7, 9, 12, tzinfo=UTC),
            results=[
                _quality_result(
                    quality_run_id=1,
                    check_name="continuity",
                    severity="error",
                    status="failed",
                    safe_detail="missing hourly interval",
                ),
                _quality_result(
                    quality_run_id=1,
                    check_name="freshness",
                    severity="warning",
                    status="passed",
                ),
            ],
        )
        _seed_quality_run(
            session,
            dataset_name="raw_snapshots",
            status="failed",
            completed_at_utc=datetime(2026, 7, 9, 13, tzinfo=UTC),
            safe_error_detail="framework failed safely",
            results=[],
        )
        session.commit()

        summaries = summarize_source_health(session)

    summary_by_dataset = {summary.dataset_name: summary for summary in summaries}
    demand_summary = summary_by_dataset["ieso_hourly_demand"]
    metadata_summary = summary_by_dataset["raw_snapshots"]
    untouched_summary = summary_by_dataset["weather_observations"]

    assert set(DATASET_CONTRACTS).issuperset(summary_by_dataset)
    assert demand_summary.latest_quality_run_status == "succeeded"
    assert demand_summary.worst_severity == "error"
    assert demand_summary.is_blocked is True
    assert demand_summary.check_counts_by_status == {"failed": 1, "passed": 1}
    assert demand_summary.latest_checked_at_utc == datetime(2026, 7, 9, 12, tzinfo=UTC)
    assert demand_summary.safe_failure_summaries == ("missing hourly interval",)
    assert metadata_summary.latest_quality_run_status == "failed"
    assert metadata_summary.worst_severity == "critical"
    assert metadata_summary.is_blocked is True
    assert metadata_summary.safe_failure_summaries == ("framework failed safely",)
    assert untouched_summary.latest_quality_run_status == "not_started"
    assert untouched_summary.worst_severity is None
    assert untouched_summary.is_blocked is False


@pytest.mark.integration
def test_quality_health_endpoint_returns_safe_summary(
    api_settings: Settings,
    clean_session_factory: sessionmaker[Session],
    live_postgres_engine: Engine,
) -> None:
    """The quality health endpoint exposes safe summary data only."""

    with clean_session_factory() as session:
        _seed_quality_run(
            session,
            dataset_name="weather_forecasts",
            status="succeeded",
            completed_at_utc=datetime(2026, 7, 9, 14, tzinfo=UTC),
            results=[
                _quality_result(
                    quality_run_id=1,
                    check_name="forecast_ranges",
                    severity="warning",
                    status="passed",
                ),
                _quality_result(
                    quality_run_id=1,
                    check_name="forecast_timestamps",
                    severity="error",
                    status="failed",
                    safe_detail="valid_time_utc is not after issue_time_utc",
                ),
            ],
        )
        session.commit()

    app = create_app(api_settings, engine=live_postgres_engine)

    with TestClient(app) as client:
        response = client.get("/quality/health")

    assert response.status_code == 200
    payload = response.json()
    forecast_summary = next(
        item for item in payload["datasets"] if item["dataset_name"] == "weather_forecasts"
    )
    assert forecast_summary["latest_quality_run_status"] == "succeeded"
    assert forecast_summary["worst_severity"] == "error"
    assert forecast_summary["is_blocked"] is True
    assert forecast_summary["check_counts_by_status"] == {"passed": 1, "failed": 1}
    assert forecast_summary["safe_failure_summaries"] == [
        "valid_time_utc is not after issue_time_utc"
    ]
    assert "secret" not in response.text


def _seed_quality_run(
    session: Session,
    *,
    dataset_name: str,
    status: str,
    completed_at_utc: datetime,
    safe_error_detail: str | None = None,
    results: list[QualityResult],
) -> None:
    quality_run = QualityRun(
        dataset_name=dataset_name,
        status=status,
        started_at_utc=completed_at_utc,
        completed_at_utc=completed_at_utc,
        safe_error_detail=safe_error_detail,
    )
    session.add(quality_run)
    session.flush()

    for result in results:
        result.quality_run_id = quality_run.id
        result.dataset_name = dataset_name
        session.add(result)


def _quality_result(
    *,
    quality_run_id: int,
    check_name: str,
    severity: str,
    status: str,
    safe_detail: str | None = None,
) -> QualityResult:
    return QualityResult(
        quality_run_id=quality_run_id,
        dataset_name="placeholder",
        check_name=check_name,
        check_category="schema",
        severity=severity,
        status=status,
        safe_detail=safe_detail,
        is_blocking=False,
        created_at_utc=datetime(2026, 7, 9, 12, tzinfo=UTC),
    )
