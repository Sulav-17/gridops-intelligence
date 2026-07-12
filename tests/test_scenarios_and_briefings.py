"""Tests for M06 scenarios, briefing facts, and backend outputs."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from gridops.api import create_app
from gridops.config import AppEnvironment, Settings
from gridops.database import Base, make_engine, make_session_factory
from gridops.decision.alert_engine import evaluate_and_persist_alerts
from gridops.decision.briefing_facts import generate_briefing
from gridops.decision.scenario_engine import run_scenario
from gridops.decision.scenario_schemas import ScenarioRequest, ScenarioType
from gridops.models import (
    BriefingFact,
    ForecastPeakOutput,
    ForecastRampOutput,
    ProductionForecastPrediction,
    ProductionForecastRun,
    QualityResult,
    QualityRun,
    ScenarioAssumption,
    ScenarioResultRow,
    ScenarioRun,
)

TEST_DATABASE_URL = "postgresql+psycopg://gridops:gridops@localhost:55432/gridops_test"
ISSUE_TIME = datetime(2026, 1, 10, 12, tzinfo=UTC)
CREATED_AT = datetime(2026, 7, 10, 15, tzinfo=UTC)


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
    """Create a clean schema for scenario and briefing tests."""

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
def test_demand_growth_scenario_persists_assumptions_and_rows(
    clean_session_factory: sessionmaker[Session],
) -> None:
    """Demand growth scenarios apply percent growth and added MW deterministically."""

    with clean_session_factory() as session:
        forecast_run = _seed_forecast_run(
            session,
            values=(Decimal("10000.000"), Decimal("12000.000")),
        )
        result = run_scenario(
            session,
            request=ScenarioRequest(
                production_forecast_run_id=forecast_run.id,
                scenario_type=ScenarioType.DEMAND_GROWTH,
                generated_at_utc=CREATED_AT,
                demand_growth_percent=Decimal("2.5"),
                added_load_mw=Decimal("100.000"),
            ),
        )
        session.commit()

        assumptions = list(session.scalars(select(ScenarioAssumption)).all())
        rows = list(
            session.scalars(
                select(ScenarioResultRow).order_by(ScenarioResultRow.target_interval_start_utc)
            ).all()
        )

    assert result.scenario_run.scenario_type == "demand_growth"
    assert {assumption.assumption_name for assumption in assumptions} >= {
        "demand_growth_percent",
        "added_load_mw",
    }
    assert [row.delta_mw for row in rows] == [Decimal("350.000"), Decimal("400.000")]
    assert [row.scenario_value_mw for row in rows] == [
        Decimal("10350.000"),
        Decimal("12400.000"),
    ]


@pytest.mark.integration
def test_weather_adjustment_scenario_records_limitation(
    clean_session_factory: sessionmaker[Session],
) -> None:
    """Weather scenarios use an explicitly limited deterministic approximation."""

    with clean_session_factory() as session:
        forecast_run = _seed_forecast_run(session, values=(Decimal("10000.000"),))
        result = run_scenario(
            session,
            request=ScenarioRequest(
                production_forecast_run_id=forecast_run.id,
                scenario_type=ScenarioType.WEATHER_ADJUSTMENT,
                generated_at_utc=CREATED_AT,
                temperature_delta_c=Decimal("3.0"),
            ),
        )
        session.commit()

        row = session.scalar(select(ScenarioResultRow))
        scenario = session.get(ScenarioRun, result.scenario_run.id)

    assert row is not None
    assert row.delta_mw == Decimal("225.000")
    assert scenario is not None
    assert "weather_adjustment_method" in scenario.limitations_json
    assert scenario.limitations_json["scenario_outputs_are_predictions"] is False


@pytest.mark.integration
def test_combined_weather_load_scenario(
    clean_session_factory: sessionmaker[Session],
) -> None:
    """Combined scenarios add deterministic load and weather deltas."""

    with clean_session_factory() as session:
        forecast_run = _seed_forecast_run(session, values=(Decimal("10000.000"),))
        run_scenario(
            session,
            request=ScenarioRequest(
                production_forecast_run_id=forecast_run.id,
                scenario_type=ScenarioType.COMBINED_WEATHER_LOAD,
                generated_at_utc=CREATED_AT,
                demand_growth_percent=Decimal("1.0"),
                added_load_mw=Decimal("50.000"),
                temperature_delta_c=Decimal("2.0"),
            ),
        )
        session.commit()

        row = session.scalar(select(ScenarioResultRow))

    assert row is not None
    assert row.delta_mw == Decimal("300.000")
    assert row.scenario_value_mw == Decimal("10300.000")


@pytest.mark.integration
def test_briefing_fact_generation_includes_required_facts(
    clean_session_factory: sessionmaker[Session],
) -> None:
    """Briefing facts summarize forecast, alerts, source health, and scenarios."""

    with clean_session_factory() as session:
        forecast_run = _seed_forecast_run(
            session,
            values=(Decimal("24100.000"), Decimal("26000.000"), Decimal("25200.000")),
        )
        _seed_peak_and_ramp(session, forecast_run)
        _seed_quality_state(session)
        evaluate_and_persist_alerts(
            session,
            production_forecast_run_id=forecast_run.id,
            generated_at_utc=CREATED_AT,
        )
        run_scenario(
            session,
            request=ScenarioRequest(
                production_forecast_run_id=forecast_run.id,
                scenario_type=ScenarioType.DEMAND_GROWTH,
                generated_at_utc=CREATED_AT,
                demand_growth_percent=Decimal("1.0"),
            ),
        )

        result = generate_briefing(
            session,
            production_forecast_run_id=forecast_run.id,
            generated_at_utc=CREATED_AT,
        )
        session.commit()

        facts = list(session.scalars(select(BriefingFact)).all())
        facts_by_type = {fact.fact_type: fact for fact in facts}

    assert result.briefing_run.status == "succeeded"
    assert {
        "forecast_issue",
        "expected_peak",
        "largest_ramp",
        "open_alert_summary",
        "source_health_summary",
        "quality_limitations",
        "model_confidence_limitations",
        "scenario_highlights",
        "known_limitations",
    }.issubset(facts_by_type)
    assert facts_by_type["expected_peak"].fact_value_json["peak_demand_mw"] == "26000.000"
    assert facts_by_type["largest_ramp"].fact_value_json["absolute_ramp_mw"] == "1900.000"
    open_alert_count = cast(
        int,
        facts_by_type["open_alert_summary"].fact_value_json["open_alert_count"],
    )
    assert open_alert_count >= 1
    source_health = cast(
        list[dict[str, object]],
        facts_by_type["source_health_summary"].fact_value_json["datasets"],
    )
    assert any(item["dataset_name"] == "weather_forecasts" for item in source_health)
    assert (
        facts_by_type["model_confidence_limitations"].fact_value_json[
            "true_prediction_intervals_available"
        ]
        is False
    )
    claims_excluded = cast(
        list[str],
        facts_by_type["known_limitations"].fact_value_json["claims_excluded"],
    )
    assert facts_by_type["known_limitations"].fact_value_json["narrative_generated"] is False
    assert "official_grid_emergency_status" in claims_excluded


@pytest.mark.integration
def test_scenario_and_briefing_api_outputs(
    api_settings: Settings,
    clean_session_factory: sessionmaker[Session],
    live_postgres_engine: Engine,
) -> None:
    """Scenario and briefing endpoints expose persisted structured outputs."""

    with clean_session_factory() as session:
        forecast_run = _seed_forecast_run(session, values=(Decimal("10000.000"),))
        _seed_peak_and_ramp(session, forecast_run)
        session.commit()
        forecast_run_id = forecast_run.id

    app = create_app(api_settings, engine=live_postgres_engine)
    with TestClient(app) as client:
        scenario_response = client.post(
            "/scenarios",
            json={
                "production_forecast_run_id": forecast_run_id,
                "scenario_type": "demand_growth",
                "generated_at_utc": CREATED_AT.isoformat(),
                "demand_growth_percent": "1.0",
                "added_load_mw": "25.000",
            },
        )
        briefing_response = client.post(
            "/briefings/generate",
            json={
                "production_forecast_run_id": forecast_run_id,
                "generated_at_utc": CREATED_AT.isoformat(),
            },
        )
        latest_response = client.get("/briefings/latest")

    assert scenario_response.status_code == 200
    scenario_payload = scenario_response.json()
    assert scenario_payload["scenario_type"] == "demand_growth"
    assert scenario_payload["result_rows"][0]["delta_mw"] == "125.000"
    assert briefing_response.status_code == 200
    assert latest_response.status_code == 200
    latest_payload = latest_response.json()
    assert any(fact["fact_type"] == "expected_peak" for fact in latest_payload["facts"])
    assert "secret" not in latest_response.text


@pytest.mark.integration
def test_m06_scenario_and_briefing_tables_exist(
    clean_session_factory: sessionmaker[Session],
    live_postgres_engine: Engine,
) -> None:
    """M06 Chunk 2 tables are represented in the database schema."""

    table_names = set(inspect(live_postgres_engine).get_table_names())

    assert {
        "scenario_runs",
        "scenario_assumptions",
        "scenario_result_rows",
        "briefing_runs",
        "briefing_facts",
    }.issubset(table_names)


def _seed_forecast_run(
    session: Session,
    *,
    values: tuple[Decimal, ...],
) -> ProductionForecastRun:
    run = ProductionForecastRun(
        model_name="decision_test_model",
        model_type="test_model",
        model_version="m06-c02",
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


def _seed_quality_state(session: Session) -> None:
    quality_run = QualityRun(
        dataset_name="weather_forecasts",
        status="succeeded",
        started_at_utc=CREATED_AT,
        completed_at_utc=CREATED_AT,
    )
    session.add(quality_run)
    session.flush()
    result = QualityResult(
        quality_run_id=quality_run.id,
        dataset_name="weather_forecasts",
        check_name="fixture_weather_freshness",
        check_category="freshness",
        severity="warning",
        status="failed",
        safe_detail="weather forecast fixture stale",
        is_blocking=False,
        created_at_utc=CREATED_AT,
    )
    session.add(result)
    session.flush()
