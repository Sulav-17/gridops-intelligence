"""Tests for M06 alert API endpoints and decision runner commands."""

import json
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
from gridops.decision.runner import main as decision_runner_main
from gridops.models import (
    ForecastPeakOutput,
    ForecastRampOutput,
    ProductionForecastPrediction,
    ProductionForecastRun,
)

TEST_DATABASE_URL = "postgresql+psycopg://gridops:gridops@localhost:55432/gridops_test"
ISSUE_TIME = datetime(2026, 1, 10, 12, tzinfo=UTC)
CREATED_AT = datetime(2026, 7, 10, 16, tzinfo=UTC)


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
    """Create a clean schema for decision API tests."""

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
def test_alert_api_evaluates_lists_details_and_transitions_state(
    api_settings: Settings,
    clean_session_factory: sessionmaker[Session],
    live_postgres_engine: Engine,
) -> None:
    """Alert API exposes evaluation evidence and lifecycle transitions."""

    with clean_session_factory() as session:
        forecast_run = _seed_forecast_run(session, values=(Decimal("24100.000"),))
        session.commit()
        forecast_run_id = forecast_run.id

    app = create_app(api_settings, engine=live_postgres_engine)
    with TestClient(app) as client:
        evaluate = client.post(
            "/alerts/evaluate",
            json={
                "production_forecast_run_id": forecast_run_id,
                "generated_at_utc": CREATED_AT.isoformat(),
            },
        )
        alert_id = evaluate.json()["alerts"][0]["alert_id"]
        listed = client.get("/alerts")
        detail = client.get(f"/alerts/{alert_id}")
        transition = client.patch(
            f"/alerts/{alert_id}/state",
            json={
                "state": "acknowledged",
                "changed_at_utc": (CREATED_AT + timedelta(minutes=1)).isoformat(),
                "reason": "reviewed in api test",
            },
        )

    assert evaluate.status_code == 200
    assert evaluate.json()["created_count"] == 1
    assert listed.status_code == 200
    assert listed.json()["alerts"][0]["current_evidence"]["forecast_value_mw"] == "24100.000"
    assert detail.status_code == 200
    assert detail.json()["evidence_records"][0]["evidence"]["threshold_mw"] == "24000.000"
    assert detail.json()["lifecycle_history"][0]["to_state"] == "open"
    assert transition.status_code == 200
    assert transition.json()["state"] == "acknowledged"
    assert transition.json()["lifecycle_history"][-1]["transition_reason"] == "reviewed in api test"


@pytest.mark.integration
def test_alert_api_rejects_invalid_transition(
    api_settings: Settings,
    clean_session_factory: sessionmaker[Session],
    live_postgres_engine: Engine,
) -> None:
    """Invalid lifecycle transitions return a safe 400 response."""

    with clean_session_factory() as session:
        forecast_run = _seed_forecast_run(session, values=(Decimal("24100.000"),))
        session.commit()
        forecast_run_id = forecast_run.id

    app = create_app(api_settings, engine=live_postgres_engine)
    with TestClient(app) as client:
        evaluate = client.post(
            "/alerts/evaluate",
            json={
                "production_forecast_run_id": forecast_run_id,
                "generated_at_utc": CREATED_AT.isoformat(),
            },
        )
        alert_id = evaluate.json()["alerts"][0]["alert_id"]
        resolved = client.patch(
            f"/alerts/{alert_id}/state",
            json={"state": "resolved", "changed_at_utc": CREATED_AT.isoformat()},
        )
        invalid = client.patch(
            f"/alerts/{alert_id}/state",
            json={"state": "open", "changed_at_utc": CREATED_AT.isoformat()},
        )

    assert resolved.status_code == 200
    assert invalid.status_code == 400
    assert "invalid alert lifecycle transition" in invalid.json()["detail"]


@pytest.mark.integration
def test_decision_runner_commands_emit_json(
    clean_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Decision runner commands evaluate alerts, run scenarios, and generate briefings."""

    with clean_session_factory() as session:
        forecast_run = _seed_forecast_run(
            session,
            values=(Decimal("24100.000"), Decimal("26000.000")),
        )
        _seed_peak_and_ramp(session, forecast_run)
        session.commit()
        forecast_run_id = forecast_run.id

    monkeypatch.setenv("GRIDOPS_DATABASE_URL", TEST_DATABASE_URL)

    assert (
        decision_runner_main(
            [
                "evaluate-alerts",
                "--forecast-run-id",
                str(forecast_run_id),
                "--generated-at-utc",
                CREATED_AT.isoformat(),
            ]
        )
        == 0
    )
    alerts_payload = json.loads(capsys.readouterr().out)
    assert alerts_payload["command"] == "evaluate-alerts"
    assert alerts_payload["created_count"] >= 1

    assert (
        decision_runner_main(
            [
                "run-scenario",
                "--forecast-run-id",
                str(forecast_run_id),
                "--load-growth-percent",
                "2",
                "--generated-at-utc",
                CREATED_AT.isoformat(),
            ]
        )
        == 0
    )
    scenario_payload = json.loads(capsys.readouterr().out)
    assert scenario_payload["command"] == "run-scenario"
    assert scenario_payload["scenario_type"] == "demand_growth"

    assert (
        decision_runner_main(
            [
                "generate-briefing",
                "--forecast-run-id",
                str(forecast_run_id),
                "--generated-at-utc",
                CREATED_AT.isoformat(),
            ]
        )
        == 0
    )
    briefing_payload = json.loads(capsys.readouterr().out)
    assert briefing_payload["command"] == "generate-briefing"
    assert briefing_payload["fact_count"] >= 1


def _seed_forecast_run(
    session: Session,
    *,
    values: tuple[Decimal, ...],
) -> ProductionForecastRun:
    run = ProductionForecastRun(
        model_name="decision_api_test_model",
        model_type="test_model",
        model_version="m06-c03",
        feature_version="m04_c01_foundation",
        forecast_issue_time_utc=ISSUE_TIME,
        status="succeeded",
        started_at_utc=CREATED_AT,
        completed_at_utc=CREATED_AT,
        created_at_utc=CREATED_AT,
    )
    session.add(run)
    session.flush()

    for index, value in enumerate(values, start=1):
        target_start = ISSUE_TIME + timedelta(hours=index)
        prediction = ProductionForecastPrediction(
            production_forecast_run_id=run.id,
            forecast_issue_time_utc=ISSUE_TIME,
            target_interval_start_utc=target_start,
            target_interval_end_utc=target_start + timedelta(hours=1),
            lead_hour=index,
            p50_demand_mw=value,
            prediction_type="p50_only",
            created_at_utc=CREATED_AT,
        )
        session.add(prediction)
    session.flush()
    return run


def _seed_peak_and_ramp(session: Session, forecast_run: ProductionForecastRun) -> None:
    peak = ForecastPeakOutput(
        production_forecast_run_id=forecast_run.id,
        peak_target_interval_start_utc=ISSUE_TIME + timedelta(hours=2),
        peak_target_interval_end_utc=ISSUE_TIME + timedelta(hours=3),
        peak_demand_mw=Decimal("26000.000"),
        peak_lead_hour=2,
        created_at_utc=CREATED_AT,
    )
    ramp = ForecastRampOutput(
        production_forecast_run_id=forecast_run.id,
        target_interval_start_utc=ISSUE_TIME + timedelta(hours=2),
        previous_target_interval_start_utc=ISSUE_TIME + timedelta(hours=1),
        forecast_ramp_mw=Decimal("1900.000"),
        absolute_ramp_mw=Decimal("1900.000"),
        created_at_utc=CREATED_AT,
    )
    session.add_all([peak, ramp])
    session.flush()
