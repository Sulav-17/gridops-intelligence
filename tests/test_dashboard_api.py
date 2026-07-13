"""Integration tests for the M07-C01 dashboard API contract."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from gridops.api import create_app
from gridops.config import AppEnvironment, Settings
from gridops.database import Base, make_engine, make_session_factory
from gridops.models import (
    BaselineForecastRun,
    BaselineMetricResult,
    ForecastPeakOutput,
    ForecastRampOutput,
    ModelPerformanceSummary,
    ProductionForecastPrediction,
    ProductionForecastRun,
)

TEST_DATABASE_URL = "postgresql+psycopg://gridops:gridops@localhost:55432/gridops_test"
ISSUE_TIME = datetime(2026, 7, 12, 10, tzinfo=UTC)
CREATED_AT = datetime(2026, 7, 12, 11, tzinfo=UTC)


@pytest.fixture
def live_postgres_engine() -> Generator[Engine, None, None]:
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
    Base.metadata.drop_all(live_postgres_engine)
    Base.metadata.create_all(live_postgres_engine)
    try:
        yield make_session_factory(live_postgres_engine)
    finally:
        Base.metadata.drop_all(live_postgres_engine)


def _settings(*, demo_mode: bool = False) -> Settings:
    return Settings(
        app_environment=AppEnvironment.TEST,
        database_url=SecretStr(TEST_DATABASE_URL),
        demo_mode=demo_mode,
    )


@pytest.mark.integration
def test_dashboard_reads_handle_empty_and_missing_forecast(
    clean_session_factory: sessionmaker[Session],
    live_postgres_engine: Engine,
) -> None:
    app = create_app(_settings(), engine=live_postgres_engine)
    with TestClient(app) as client:
        overview = client.get("/dashboard/overview")
        latest = client.get("/forecasts/latest")
        missing = client.get("/forecasts/999")
        performance = client.get("/model-performance/latest")
        system = client.get("/system/status")

    assert overview.status_code == 200
    assert overview.json()["forecast"] is None
    assert overview.json()["active_alert_count"] == 0
    assert latest.status_code == 404
    assert missing.status_code == 404
    assert performance.status_code == 200
    assert performance.json()["production_metrics"] == []
    assert system.status_code == 200
    assert system.json() == {
        "status": "ready",
        "database": "ready",
        "demo_mode": False,
        "latest_runs": {
            "ingestion": None,
            "quality": None,
            "forecast": None,
            "alert_evaluation": None,
            "briefing": None,
        },
    }
    assert "postgresql" not in system.text
    assert "localhost" not in system.text


@pytest.mark.integration
def test_forecast_and_verified_metric_reads(
    clean_session_factory: sessionmaker[Session],
    live_postgres_engine: Engine,
) -> None:
    with clean_session_factory() as session:
        run = _seed_forecast(session)
        _seed_metrics(session)
        session.commit()
        run_id = run.id

    app = create_app(_settings(), engine=live_postgres_engine)
    with TestClient(app) as client:
        latest = client.get("/forecasts/latest")
        detail = client.get(f"/forecasts/{run_id}")
        overview = client.get("/dashboard/overview")
        performance = client.get("/model-performance/latest")

    assert latest.status_code == 200
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["forecast_run_id"] == run_id
    assert payload["predictions"][0]["p50_demand_mw"] == "10000.000"
    assert payload["predictions"][0]["p10_demand_mw"] is None
    assert payload["predictions"][0]["p90_demand_mw"] is None
    assert payload["intervals_available"] is False
    assert payload["peak"]["peak_demand_mw"] == "11000.000"
    assert len(payload["ramps"]) == 1
    assert overview.json()["forecast"]["forecast_run_id"] == run_id
    metrics = performance.json()
    assert metrics["production_metrics"][0]["metric_name"] == "mae"
    assert metrics["production_metrics"][0]["metric_value"] == "125.000000"
    assert metrics["baseline"]["metrics"][0]["metric_value"] == "250.000000"
    assert metrics["limitations"]["metrics_are_persisted_not_presentation_calculated"] is True


@pytest.mark.integration
def test_demo_mode_restricts_mutations_and_bounds_scenarios(
    clean_session_factory: sessionmaker[Session],
    live_postgres_engine: Engine,
) -> None:
    with clean_session_factory() as session:
        run = _seed_forecast(session)
        session.commit()
        run_id = run.id

    app = create_app(_settings(demo_mode=True), engine=live_postgres_engine)
    with TestClient(app) as client:
        alert_evaluation = client.post(
            "/alerts/evaluate", json={"production_forecast_run_id": run_id}
        )
        alert_state = client.patch("/alerts/1/state", json={"state": "acknowledged"})
        briefing = client.post("/briefings/generate", json={"production_forecast_run_id": run_id})
        accepted = client.post(
            "/scenarios",
            json={
                "production_forecast_run_id": run_id,
                "scenario_type": "combined_weather_load",
                "demand_growth_percent": "10",
                "added_load_mw": "2000",
                "temperature_delta_c": "-10",
                "humidity_delta_percent": "30",
            },
        )
        rejected = client.post(
            "/scenarios",
            json={
                "production_forecast_run_id": run_id,
                "scenario_type": "demand_growth",
                "demand_growth_percent": "10.001",
            },
        )
        non_finite = client.post(
            "/scenarios",
            json={
                "production_forecast_run_id": run_id,
                "scenario_type": "demand_growth",
                "demand_growth_percent": "NaN",
            },
        )

    assert alert_evaluation.status_code == 403
    assert alert_state.status_code == 403
    assert briefing.status_code == 403
    assert accepted.status_code == 200
    assert accepted.json()["limitations"]["scenario_outputs_are_predictions"] is False
    assert rejected.status_code == 400
    assert "demand_growth_percent" in rejected.json()["detail"]
    assert non_finite.status_code == 400
    assert non_finite.json()["detail"] == "scenario values must be finite"


def _seed_forecast(session: Session) -> ProductionForecastRun:
    run = ProductionForecastRun(
        model_name="dashboard_fixture_model",
        model_type="test_model",
        model_version="m07-c01",
        feature_version="m04_c01_foundation",
        forecast_issue_time_utc=ISSUE_TIME,
        status="succeeded",
        quality_status="trusted",
        started_at_utc=CREATED_AT,
        completed_at_utc=CREATED_AT,
        created_at_utc=CREATED_AT,
    )
    session.add(run)
    session.flush()
    for lead_hour, value in enumerate((Decimal("10000.000"), Decimal("11000.000")), start=1):
        target = ISSUE_TIME + timedelta(hours=lead_hour)
        session.add(
            ProductionForecastPrediction(
                production_forecast_run_id=run.id,
                forecast_issue_time_utc=ISSUE_TIME,
                target_interval_start_utc=target,
                target_interval_end_utc=target + timedelta(hours=1),
                lead_hour=lead_hour,
                p50_demand_mw=value,
                prediction_type="p50_only",
                created_at_utc=CREATED_AT,
            )
        )
    session.flush()
    session.add_all(
        [
            ForecastPeakOutput(
                production_forecast_run_id=run.id,
                peak_target_interval_start_utc=ISSUE_TIME + timedelta(hours=2),
                peak_target_interval_end_utc=ISSUE_TIME + timedelta(hours=3),
                peak_demand_mw=Decimal("11000.000"),
                peak_lead_hour=2,
                created_at_utc=CREATED_AT,
            ),
            ForecastRampOutput(
                production_forecast_run_id=run.id,
                target_interval_start_utc=ISSUE_TIME + timedelta(hours=2),
                previous_target_interval_start_utc=ISSUE_TIME + timedelta(hours=1),
                forecast_ramp_mw=Decimal("1000.000"),
                absolute_ramp_mw=Decimal("1000.000"),
                created_at_utc=CREATED_AT,
            ),
        ]
    )
    session.flush()
    return run


def _seed_metrics(session: Session) -> None:
    baseline = BaselineForecastRun(
        baseline_name="same_hour_yesterday",
        feature_version="m04_c01_foundation",
        status="succeeded",
        evaluation_window_start_utc=ISSUE_TIME - timedelta(days=1),
        evaluation_window_end_utc=ISSUE_TIME,
        started_at_utc=CREATED_AT - timedelta(hours=1),
        completed_at_utc=CREATED_AT,
    )
    session.add(baseline)
    session.flush()
    session.add(
        BaselineMetricResult(
            baseline_forecast_run_id=baseline.id,
            metric_name="mae",
            metric_value=Decimal("250.000000"),
            metric_unit="MW",
            evaluation_window_start_utc=ISSUE_TIME - timedelta(days=1),
            evaluation_window_end_utc=ISSUE_TIME,
            created_at_utc=CREATED_AT,
        )
    )
    session.add(
        ModelPerformanceSummary(
            model_name="dashboard_fixture_model",
            model_type="test_model",
            model_version="m07-c01",
            feature_version="m04_c01_foundation",
            metric_name="mae",
            metric_value=Decimal("125.000000"),
            metric_unit="MW",
            row_count=2,
            evaluation_window_start_utc=ISSUE_TIME - timedelta(days=1),
            evaluation_window_end_utc=ISSUE_TIME,
            created_at_utc=CREATED_AT,
        )
    )
    session.flush()
