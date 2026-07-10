"""Tests for the M05 production forecasting and MLOps schema."""

from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy import inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from gridops.config import Settings
from gridops.database import Base, make_engine, make_session_factory
from gridops.forecasting.model_contracts import (
    ForecastRunStatus,
    ModelArtifactStatus,
    ModelSelectionStatus,
    ModelTrainingStatus,
)
from gridops.forecasting.models import (
    ForecastPeakOutput,
    ForecastRampOutput,
    ModelArtifact,
    ModelDriftSummary,
    ModelPerformanceSummary,
    ModelSelectionResult,
    ModelTrainingRun,
    ProductionForecastPrediction,
    ProductionForecastRun,
)

TEST_DATABASE_URL = "postgresql+psycopg://gridops:gridops@localhost:55432/gridops_test"

M05_TABLE_NAMES = {
    "model_training_runs",
    "model_artifacts",
    "model_selection_results",
    "production_forecast_runs",
    "production_forecast_predictions",
    "forecast_peak_outputs",
    "forecast_ramp_outputs",
    "model_performance_summaries",
    "model_drift_summaries",
}

FUTURE_NON_ALERT_TABLE_NAMES = {
    "alert_events",
    "alert_lifecycle",
    "scenarios",
    "scenario_runs",
    "briefings",
    "dashboard_views",
    "deployments",
    "deployment_state",
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


@pytest.fixture
def clean_session_factory(
    live_postgres_engine: Engine,
) -> Generator[sessionmaker[Session], None, None]:
    """Create a clean schema for M05 schema persistence tests."""

    Base.metadata.drop_all(live_postgres_engine)
    Base.metadata.create_all(live_postgres_engine)

    try:
        yield make_session_factory(live_postgres_engine)
    finally:
        Base.metadata.drop_all(live_postgres_engine)


def test_m05_models_import_cleanly_and_do_not_include_future_product_tables() -> None:
    """M05 ORM exports point to the requested tables and avoid future non-alert scope."""

    assert ModelTrainingRun.__tablename__ == "model_training_runs"
    assert ModelArtifact.__tablename__ == "model_artifacts"
    assert ModelSelectionResult.__tablename__ == "model_selection_results"
    assert ProductionForecastRun.__tablename__ == "production_forecast_runs"
    assert ProductionForecastPrediction.__tablename__ == "production_forecast_predictions"
    assert ForecastPeakOutput.__tablename__ == "forecast_peak_outputs"
    assert ForecastRampOutput.__tablename__ == "forecast_ramp_outputs"
    assert ModelPerformanceSummary.__tablename__ == "model_performance_summaries"
    assert ModelDriftSummary.__tablename__ == "model_drift_summaries"
    assert FUTURE_NON_ALERT_TABLE_NAMES.isdisjoint(Base.metadata.tables)


@pytest.mark.integration
def test_m05_migration_creates_expected_tables(
    live_postgres_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Alembic can upgrade a clean database to include the M05 schema."""

    Base.metadata.drop_all(live_postgres_engine)
    with live_postgres_engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")

    monkeypatch.setenv("GRIDOPS_DATABASE_URL", TEST_DATABASE_URL)
    command.upgrade(Config("alembic.ini"), "head")

    inspector = inspect(live_postgres_engine)
    table_names = set(inspector.get_table_names())
    prediction_columns = {
        column["name"] for column in inspector.get_columns("production_forecast_predictions")
    }
    selection_columns = {
        column["name"] for column in inspector.get_columns("model_selection_results")
    }

    assert M05_TABLE_NAMES.issubset(table_names)
    assert FUTURE_NON_ALERT_TABLE_NAMES.isdisjoint(table_names)
    assert {
        "forecast_issue_time_utc",
        "target_interval_start_utc",
        "target_interval_end_utc",
        "lead_hour",
        "p10_demand_mw",
        "p50_demand_mw",
        "p90_demand_mw",
        "point_forecast_demand_mw",
        "prediction_type",
        "lineage_metadata",
    }.issubset(prediction_columns)
    assert {"candidate_metrics_json", "baseline_metrics_json", "selection_reason"}.issubset(
        selection_columns
    )


@pytest.mark.integration
def test_base_metadata_drop_all_handles_m05_feature_snapshot_dependencies(
    live_postgres_engine: Engine,
) -> None:
    """Registered M05 metadata lets normal drop_all order handle forecast-output FKs."""

    Base.metadata.drop_all(live_postgres_engine)
    Base.metadata.create_all(live_postgres_engine)

    inspector = inspect(live_postgres_engine)
    prediction_fks = inspector.get_foreign_keys("production_forecast_predictions")

    assert any(
        fk["referred_table"] == "feature_snapshot_rows"
        and fk["constrained_columns"] == ["feature_snapshot_row_id"]
        for fk in prediction_fks
    )

    Base.metadata.drop_all(live_postgres_engine)

    remaining_tables = set(inspect(live_postgres_engine).get_table_names())
    assert M05_TABLE_NAMES.isdisjoint(remaining_tables)
    assert "feature_snapshot_rows" not in remaining_tables


@pytest.mark.integration
def test_m05_orm_insert_read_representative_rows(
    clean_session_factory: sessionmaker[Session],
) -> None:
    """Representative rows can be persisted and read across all M05 tables."""

    created_at = datetime(2026, 7, 10, 12, tzinfo=UTC)
    training_start = datetime(2026, 1, 1, tzinfo=UTC)
    training_end = datetime(2026, 2, 1, tzinfo=UTC)
    evaluation_start = datetime(2026, 2, 1, tzinfo=UTC)
    evaluation_end = datetime(2026, 2, 8, tzinfo=UTC)
    issue_time = datetime(2026, 2, 8, 15, tzinfo=UTC)
    target_start = datetime(2026, 2, 8, 16, tzinfo=UTC)
    target_end = datetime(2026, 2, 8, 17, tzinfo=UTC)

    with clean_session_factory() as session:
        training_run = ModelTrainingRun(
            model_name="candidate_tree",
            model_type="sklearn_random_forest",
            model_version="m05-c01-contract",
            feature_version="m04_c01_foundation",
            status=ModelTrainingStatus.SUCCEEDED.value,
            training_window_start_utc=training_start,
            training_window_end_utc=training_end,
            evaluation_window_start_utc=evaluation_start,
            evaluation_window_end_utc=evaluation_end,
            parameters_json={"max_depth": 4},
            metrics_summary_json={"mae": 10.0},
            lineage_metadata={"source": "test"},
            started_at_utc=created_at,
            completed_at_utc=created_at,
            created_at_utc=created_at,
        )
        session.add(training_run)
        session.flush()

        artifact = ModelArtifact(
            model_training_run_id=training_run.id,
            model_name="candidate_tree",
            model_type="sklearn_random_forest",
            model_version="m05-c01-contract",
            feature_version="m04_c01_foundation",
            artifact_uri="artifacts/models/candidate_tree.joblib",
            artifact_hash="a" * 64,
            status=ModelArtifactStatus.AVAILABLE.value,
            training_window_start_utc=training_start,
            training_window_end_utc=training_end,
            evaluation_window_start_utc=evaluation_start,
            evaluation_window_end_utc=evaluation_end,
            parameters_json={"max_depth": 4},
            metrics_summary_json={"mae": 10.0},
            lineage_metadata={"training_run_id": training_run.id},
            created_at_utc=created_at,
        )
        session.add(artifact)
        session.flush()

        selection = ModelSelectionResult(
            model_training_run_id=training_run.id,
            model_artifact_id=artifact.id,
            model_name="candidate_tree",
            model_type="sklearn_random_forest",
            model_version="m05-c01-contract",
            feature_version="m04_c01_foundation",
            selection_status=ModelSelectionStatus.SELECTED.value,
            selection_reason="candidate beats baseline in deterministic fixture",
            training_window_start_utc=training_start,
            training_window_end_utc=training_end,
            evaluation_window_start_utc=evaluation_start,
            evaluation_window_end_utc=evaluation_end,
            candidate_metrics_json={"mae": 10.0},
            baseline_metrics_json={"same_hour_yesterday": {"mae": 12.0}},
            lineage_metadata={"gate": "schema_test"},
            created_at_utc=created_at,
        )
        forecast_run = ProductionForecastRun(
            model_artifact_id=artifact.id,
            feature_snapshot_run_id=None,
            model_name="candidate_tree",
            model_type="sklearn_random_forest",
            model_version="m05-c01-contract",
            feature_version="m04_c01_foundation",
            forecast_issue_time_utc=issue_time,
            status=ForecastRunStatus.SUCCEEDED.value,
            quality_status="not_evaluated_in_schema_test",
            lineage_metadata={"artifact_id": artifact.id},
            started_at_utc=created_at,
            completed_at_utc=created_at,
            created_at_utc=created_at,
        )
        session.add_all([selection, forecast_run])
        session.flush()

        prediction = ProductionForecastPrediction(
            production_forecast_run_id=forecast_run.id,
            feature_snapshot_row_id=None,
            forecast_issue_time_utc=issue_time,
            target_interval_start_utc=target_start,
            target_interval_end_utc=target_end,
            lead_hour=1,
            p10_demand_mw=None,
            p50_demand_mw=Decimal("18000.000"),
            p90_demand_mw=None,
            point_forecast_demand_mw=None,
            prediction_type="p50_only",
            lineage_metadata={"feature_version": "m04_c01_foundation"},
            created_at_utc=created_at,
        )
        peak = ForecastPeakOutput(
            production_forecast_run_id=forecast_run.id,
            peak_target_interval_start_utc=target_start,
            peak_target_interval_end_utc=target_end,
            peak_demand_mw=Decimal("18000.000"),
            peak_lead_hour=1,
            lineage_metadata={"source": "prediction"},
            created_at_utc=created_at,
        )
        ramp = ForecastRampOutput(
            production_forecast_run_id=forecast_run.id,
            target_interval_start_utc=target_start,
            previous_target_interval_start_utc=datetime(2026, 2, 8, 15, tzinfo=UTC),
            forecast_ramp_mw=Decimal("250.000"),
            absolute_ramp_mw=Decimal("250.000"),
            lineage_metadata={"source": "prediction_pair"},
            created_at_utc=created_at,
        )
        performance = ModelPerformanceSummary(
            model_artifact_id=artifact.id,
            model_name="candidate_tree",
            model_type="sklearn_random_forest",
            model_version="m05-c01-contract",
            feature_version="m04_c01_foundation",
            metric_name="mae",
            metric_value=Decimal("10.000000"),
            metric_unit="MW",
            row_count=24,
            evaluation_window_start_utc=evaluation_start,
            evaluation_window_end_utc=evaluation_end,
            lineage_metadata={"source": "schema_test"},
            created_at_utc=created_at,
        )
        drift = ModelDriftSummary(
            model_artifact_id=artifact.id,
            model_name="candidate_tree",
            model_type="sklearn_random_forest",
            model_version="m05-c01-contract",
            feature_version="m04_c01_foundation",
            feature_name="lag_24h_mw",
            drift_metric_name="population_stability_index",
            drift_score=Decimal("0.010000"),
            baseline_window_start_utc=training_start,
            baseline_window_end_utc=training_end,
            comparison_window_start_utc=evaluation_start,
            comparison_window_end_utc=evaluation_end,
            summary_json={"bucket_count": 10},
            lineage_metadata={"source": "schema_test"},
            created_at_utc=created_at,
        )
        session.add_all([prediction, peak, ramp, performance, drift])
        session.commit()

        persisted_prediction = session.scalar(select(ProductionForecastPrediction))
        persisted_selection = session.scalar(select(ModelSelectionResult))
        persisted_drift = session.scalar(select(ModelDriftSummary))

    assert persisted_prediction is not None
    assert persisted_prediction.p50_demand_mw == Decimal("18000.000")
    assert persisted_prediction.p10_demand_mw is None
    assert persisted_prediction.p90_demand_mw is None
    assert persisted_selection is not None
    assert persisted_selection.candidate_metrics_json == {"mae": 10.0}
    assert persisted_drift is not None
    assert persisted_drift.summary_json == {"bucket_count": 10}
