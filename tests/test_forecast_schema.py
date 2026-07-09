"""Tests for the M04 forecasting schema foundation."""

from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from alembic import command
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy import inspect, select
from sqlalchemy.engine import Engine

from gridops.config import Settings
from gridops.database import Base, make_engine, make_session_factory
from gridops.forecasting.models import (
    BaselineForecastPrediction,
    BaselineForecastRun,
    BaselineMetricResult,
    BaselineSliceMetricResult,
    FeatureSnapshotRow,
    FeatureSnapshotRun,
    ForecastIssue,
)

TEST_DATABASE_URL = "postgresql+psycopg://gridops:gridops@localhost:55432/gridops_test"

M04_TABLE_NAMES = {
    "forecast_issues",
    "feature_snapshot_runs",
    "feature_snapshot_rows",
    "baseline_forecast_runs",
    "baseline_forecast_predictions",
    "baseline_metric_results",
    "baseline_slice_metric_results",
}

M05_OWNED_TABLE_NAMES = {
    "production_model_registry",
    "model_registry",
    "production_scheduled_forecasts",
    "scheduled_forecasts",
    "production_forecasts",
    "prediction_intervals",
    "drift_monitoring",
    "forecast_serving_state",
}


@pytest.fixture
def live_postgres_engine() -> Generator[Engine, None, None]:
    """Create an engine for the Docker-backed test database."""

    settings = Settings(database_url=SecretStr(TEST_DATABASE_URL))
    engine = make_engine(settings)

    try:
        yield engine
    finally:
        engine.dispose()


def test_forecasting_models_import_cleanly() -> None:
    """Forecasting ORM model exports point to the intended M04 tables."""

    assert ForecastIssue.__tablename__ == "forecast_issues"
    assert FeatureSnapshotRun.__tablename__ == "feature_snapshot_runs"
    assert FeatureSnapshotRow.__tablename__ == "feature_snapshot_rows"
    assert BaselineForecastRun.__tablename__ == "baseline_forecast_runs"
    assert BaselineForecastPrediction.__tablename__ == "baseline_forecast_predictions"
    assert BaselineMetricResult.__tablename__ == "baseline_metric_results"
    assert BaselineSliceMetricResult.__tablename__ == "baseline_slice_metric_results"


def test_no_future_m05_table_names_in_metadata() -> None:
    """The M04 schema foundation does not introduce M05 production tables."""

    assert M05_OWNED_TABLE_NAMES.isdisjoint(Base.metadata.tables)


@pytest.mark.integration
def test_forecast_issue_model_persists_basic_contract(
    live_postgres_engine: Engine,
) -> None:
    """The M04 forecast issue model can persist the issue contract shell."""

    Base.metadata.drop_all(live_postgres_engine)
    Base.metadata.create_all(live_postgres_engine)
    session_factory = make_session_factory(live_postgres_engine)
    issue_time = datetime(2026, 7, 9, 15, tzinfo=UTC)

    try:
        with session_factory() as session:
            issue = ForecastIssue(
                forecast_issue_time_utc=issue_time,
                horizon_length_hours=24,
                forecast_type="day_ahead_hourly_ontario_demand",
                feature_version="m04_c01_foundation",
                point_in_time_safety_rule=(
                    "features_must_be_available_at_or_before_forecast_issue_time_utc"
                ),
                status="defined",
                quality_blocking_behavior="block_on_m03_error_or_critical",
                created_at_utc=issue_time,
            )
            session.add(issue)
            session.commit()

            persisted = session.scalar(select(ForecastIssue))

        assert persisted is not None
        assert persisted.forecast_issue_time_utc == issue_time
        assert persisted.horizon_length_hours == 24
        assert persisted.status == "defined"
    finally:
        Base.metadata.drop_all(live_postgres_engine)


@pytest.mark.integration
def test_m04_migration_creates_forecasting_foundation_tables(
    live_postgres_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Alembic can upgrade a clean database to include M04 tables."""

    Base.metadata.drop_all(live_postgres_engine)
    with live_postgres_engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")

    monkeypatch.setenv("GRIDOPS_DATABASE_URL", TEST_DATABASE_URL)
    command.upgrade(Config("alembic.ini"), "head")

    inspector = inspect(live_postgres_engine)
    table_names = set(inspector.get_table_names())
    forecast_issue_columns = {column["name"] for column in inspector.get_columns("forecast_issues")}
    feature_row_columns = {
        column["name"] for column in inspector.get_columns("feature_snapshot_rows")
    }

    assert M04_TABLE_NAMES.issubset(table_names)
    assert M05_OWNED_TABLE_NAMES.isdisjoint(table_names)
    assert {
        "forecast_issue_time_utc",
        "horizon_length_hours",
        "forecast_type",
        "feature_version",
        "point_in_time_safety_rule",
        "status",
        "quality_blocking_behavior",
        "created_at_utc",
    }.issubset(forecast_issue_columns)
    assert {
        "forecast_issue_time_utc",
        "target_interval_start_utc",
        "target_interval_end_utc",
        "lead_hour",
        "feature_version",
        "quality_status",
        "lineage_metadata",
    }.issubset(feature_row_columns)
