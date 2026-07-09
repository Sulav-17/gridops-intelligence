"""Tests for M04 slice reports and baseline persistence."""

from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.engine import Engine

from gridops.config import Settings
from gridops.database import Base, make_engine, make_session_factory
from gridops.forecasting.baselines import BaselinePrediction
from gridops.forecasting.metrics import calculate_baseline_metrics
from gridops.forecasting.reports import (
    calculate_slice_metrics,
    persist_baseline_evaluation,
)
from gridops.models import (
    BaselineForecastPrediction,
    BaselineForecastRun,
    BaselineMetricResult,
    BaselineSliceMetricResult,
)

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
    """Create a clean schema for report persistence tests."""

    Base.metadata.drop_all(live_postgres_engine)
    Base.metadata.create_all(live_postgres_engine)

    try:
        yield live_postgres_engine
    finally:
        Base.metadata.drop_all(live_postgres_engine)


def test_slice_metrics_by_lead_hour() -> None:
    """Slice metrics are produced for lead-hour groups."""

    metrics = calculate_slice_metrics(
        [_prediction(1, 16, Decimal("100.0"), Decimal("90.0"))],
        dimensions=("lead_hour",),
    )

    assert {(metric.slice_name, metric.slice_value, metric.metric_name) for metric in metrics}
    assert all(metric.slice_name == "lead_hour" for metric in metrics)
    assert all(metric.slice_value == "1" for metric in metrics)


def test_slice_metrics_by_target_hour_and_day_of_week() -> None:
    """Slice metrics are produced for target hour and day-of-week groups."""

    metrics = calculate_slice_metrics(
        [
            _prediction(1, 16, Decimal("100.0"), Decimal("90.0")),
            _prediction(2, 17, Decimal("120.0"), Decimal("110.0")),
        ],
        dimensions=("target_hour", "day_of_week"),
    )

    assert ("target_hour", "16") in {(metric.slice_name, metric.slice_value) for metric in metrics}
    assert ("day_of_week", "3") in {(metric.slice_name, metric.slice_value) for metric in metrics}


@pytest.mark.integration
def test_baseline_evaluation_persistence_smoke_test(clean_engine: Engine) -> None:
    """Baseline run, prediction, aggregate metric, and slice metric rows persist."""

    session_factory = make_session_factory(clean_engine)
    predictions = [
        _prediction(1, 16, Decimal("100.0"), Decimal("90.0")),
        _prediction(2, 17, Decimal("120.0"), Decimal("110.0")),
    ]
    metrics = calculate_baseline_metrics(predictions)
    slice_metrics = calculate_slice_metrics(predictions, dimensions=("lead_hour",))

    with session_factory() as session:
        persisted = persist_baseline_evaluation(
            session,
            baseline_name="same_hour_yesterday",
            feature_version="m04_c01_foundation",
            predictions=predictions,
            metrics=metrics,
            slice_metrics=slice_metrics,
            started_at_utc=datetime(2026, 7, 9, 18, tzinfo=UTC),
            completed_at_utc=datetime(2026, 7, 9, 18, 1, tzinfo=UTC),
            training_window_start_utc=datetime(2026, 7, 1, tzinfo=UTC),
            training_window_end_utc=datetime(2026, 7, 9, 15, tzinfo=UTC),
            evaluation_window_start_utc=datetime(2026, 7, 9, 15, tzinfo=UTC),
            evaluation_window_end_utc=datetime(2026, 7, 10, 15, tzinfo=UTC),
            run_metadata={"window_strategy": "expanding"},
        )
        session.commit()

        run_count = len(session.scalars(select(BaselineForecastRun)).all())
        prediction_count = len(session.scalars(select(BaselineForecastPrediction)).all())
        metric_count = len(session.scalars(select(BaselineMetricResult)).all())
        slice_metric_count = len(session.scalars(select(BaselineSliceMetricResult)).all())

    assert persisted.run.baseline_name == "same_hour_yesterday"
    assert run_count == 1
    assert prediction_count == 2
    assert metric_count >= 4
    assert slice_metric_count >= 4


def test_no_future_m05_scope_introduced() -> None:
    """C03 does not introduce M05 production forecasting surfaces."""

    project_root = Path(__file__).resolve().parents[1]
    pyproject = (project_root / "pyproject.toml").read_text(encoding="utf-8").lower()

    assert "mlflow" not in pyproject
    assert "lightgbm" not in pyproject
    assert "xgboost" not in pyproject
    assert not (project_root / "src" / "gridops" / "forecasting" / "serving.py").exists()
    assert not (project_root / "src" / "gridops" / "forecasting" / "alerts.py").exists()
    assert not (project_root / "src" / "gridops" / "forecasting" / "scenarios.py").exists()


def _prediction(
    lead_hour: int,
    target_hour: int,
    predicted: Decimal,
    actual: Decimal,
) -> BaselinePrediction:
    target_start = datetime(2026, 7, 9, target_hour, tzinfo=UTC)
    return BaselinePrediction(
        baseline_name="same_hour_yesterday",
        forecast_issue_time_utc=datetime(2026, 7, 9, 15, tzinfo=UTC),
        target_interval_start_utc=target_start,
        target_interval_end_utc=target_start.replace(hour=target_hour + 1),
        lead_hour=lead_hour,
        predicted_demand_mw=predicted,
        actual_demand_mw=actual,
        prediction_status="predicted",
    )
