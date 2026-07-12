"""Tests for M06 deterministic alert foundation."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import SecretStr
from sqlalchemy import inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from gridops.config import Settings
from gridops.database import Base, make_engine, make_session_factory
from gridops.decision.alert_engine import evaluate_and_persist_alerts
from gridops.decision.alert_lifecycle import transition_alert_state
from gridops.decision.alert_rules import evaluate_alert_candidates
from gridops.decision.alert_schemas import (
    AlertLifecycleState,
    AlertSeverity,
    AlertType,
)
from gridops.models import (
    Alert,
    AlertEvaluationRun,
    AlertEvidence,
    AlertLifecycleHistory,
    ForecastRampOutput,
    ProductionForecastPrediction,
    ProductionForecastRun,
    QualityResult,
    QualityRun,
)

TEST_DATABASE_URL = "postgresql+psycopg://gridops:gridops@localhost:55432/gridops_test"
ISSUE_TIME = datetime(2026, 1, 10, 12, tzinfo=UTC)
CREATED_AT = datetime(2026, 7, 10, 14, tzinfo=UTC)


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
    """Create a clean schema for alert tests."""

    Base.metadata.drop_all(live_postgres_engine)
    Base.metadata.create_all(live_postgres_engine)

    try:
        yield make_session_factory(live_postgres_engine)
    finally:
        Base.metadata.drop_all(live_postgres_engine)


def test_alert_severity_and_lifecycle_models() -> None:
    """Alert enums expose the M06 contract values."""

    assert [severity.value for severity in AlertSeverity] == [
        "info",
        "watch",
        "warning",
        "critical",
    ]
    assert {state.value for state in AlertLifecycleState} == {
        "open",
        "acknowledged",
        "resolved",
        "suppressed",
        "expired",
    }
    assert AlertType.HIGH_DEMAND.value == "high_demand"


@pytest.mark.integration
def test_high_demand_alert_triggered(clean_session_factory: sessionmaker[Session]) -> None:
    """High demand alerts trigger when a forecast exceeds the fixed threshold."""

    with clean_session_factory() as session:
        forecast_run = _seed_forecast_run(session, values=(Decimal("24100.000"),))

        candidates = evaluate_alert_candidates(
            session,
            production_forecast_run_id=forecast_run.id,
            generated_at_utc=CREATED_AT,
        )

    high_demand = [item for item in candidates if item.alert_type is AlertType.HIGH_DEMAND]
    assert len(high_demand) == 1
    assert high_demand[0].severity is AlertSeverity.WARNING
    assert high_demand[0].evidence["threshold_mw"] == "24000.000"


@pytest.mark.integration
def test_high_demand_alert_not_triggered(clean_session_factory: sessionmaker[Session]) -> None:
    """High demand alerts do not trigger below the documented threshold."""

    with clean_session_factory() as session:
        forecast_run = _seed_forecast_run(session, values=(Decimal("23999.000"),))

        candidates = evaluate_alert_candidates(
            session,
            production_forecast_run_id=forecast_run.id,
            generated_at_utc=CREATED_AT,
        )

    assert not [item for item in candidates if item.alert_type is AlertType.HIGH_DEMAND]


@pytest.mark.integration
def test_ramp_alert_triggered_from_m05_ramp_output(
    clean_session_factory: sessionmaker[Session],
) -> None:
    """Ramp alerts prefer persisted M05 ramp output evidence."""

    with clean_session_factory() as session:
        forecast_run = _seed_forecast_run(
            session,
            values=(Decimal("10000.000"), Decimal("11250.000")),
        )
        _seed_ramp_output(session, forecast_run, ramp_mw=Decimal("1250.000"))

        candidates = evaluate_alert_candidates(
            session,
            production_forecast_run_id=forecast_run.id,
            generated_at_utc=CREATED_AT,
        )

    ramps = [item for item in candidates if item.alert_type is AlertType.RAMP]
    assert len(ramps) == 1
    assert ramps[0].evidence["ramp_source"] == "forecast_ramp_outputs"
    assert ramps[0].evidence["direction"] == "up"


@pytest.mark.integration
def test_ramp_alert_not_triggered(clean_session_factory: sessionmaker[Session]) -> None:
    """Ramp alerts do not trigger below the fixed threshold."""

    with clean_session_factory() as session:
        forecast_run = _seed_forecast_run(
            session,
            values=(Decimal("10000.000"), Decimal("10800.000")),
        )

        candidates = evaluate_alert_candidates(
            session,
            production_forecast_run_id=forecast_run.id,
            generated_at_utc=CREATED_AT,
        )

    assert not [item for item in candidates if item.alert_type is AlertType.RAMP]


@pytest.mark.integration
def test_forecast_deviation_alert_triggered(
    clean_session_factory: sessionmaker[Session],
) -> None:
    """Deviation alerts compare current output to the previous succeeded run."""

    with clean_session_factory() as session:
        _seed_forecast_run(
            session,
            values=(Decimal("10000.000"),),
            forecast_issue_time_utc=ISSUE_TIME - timedelta(hours=1),
        )
        current = _seed_forecast_run(session, values=(Decimal("10850.000"),))

        candidates = evaluate_alert_candidates(
            session,
            production_forecast_run_id=current.id,
            generated_at_utc=CREATED_AT,
        )

    deviations = [item for item in candidates if item.alert_type is AlertType.FORECAST_DEVIATION]
    assert len(deviations) == 1
    assert (
        deviations[0].evidence["comparison_source"] == "previous_succeeded_production_forecast_run"
    )
    assert deviations[0].evidence["absolute_deviation_mw"] == "850.000"


@pytest.mark.integration
def test_forecast_deviation_alert_not_triggered(
    clean_session_factory: sessionmaker[Session],
) -> None:
    """Deviation alerts do not trigger when previous-run difference is small."""

    with clean_session_factory() as session:
        _seed_forecast_run(
            session,
            values=(Decimal("10000.000"),),
            forecast_issue_time_utc=ISSUE_TIME - timedelta(hours=1),
        )
        current = _seed_forecast_run(session, values=(Decimal("10700.000"),))

        candidates = evaluate_alert_candidates(
            session,
            production_forecast_run_id=current.id,
            generated_at_utc=CREATED_AT,
        )

    assert not [item for item in candidates if item.alert_type is AlertType.FORECAST_DEVIATION]


@pytest.mark.integration
def test_source_health_context_alert_from_m03_quality_data(
    clean_session_factory: sessionmaker[Session],
) -> None:
    """Source-health alerts are generated from persisted M03 quality state."""

    with clean_session_factory() as session:
        forecast_run = _seed_forecast_run(session, values=(Decimal("10000.000"),))
        _seed_quality_state(
            session,
            dataset_name="weather_forecasts",
            severity="error",
            status="failed",
            safe_detail="missing forecast intervals",
        )

        candidates = evaluate_alert_candidates(
            session,
            production_forecast_run_id=forecast_run.id,
            generated_at_utc=CREATED_AT,
        )

    source_health = [item for item in candidates if item.alert_type is AlertType.SOURCE_HEALTH]
    assert len(source_health) == 1
    assert source_health[0].severity is AlertSeverity.CRITICAL
    assert source_health[0].evidence["dataset_name"] == "weather_forecasts"
    assert source_health[0].evidence["safe_failure_summaries"] == ["missing forecast intervals"]


@pytest.mark.integration
def test_combined_context_alert(clean_session_factory: sessionmaker[Session]) -> None:
    """Combined context alerts include deterministic component signals."""

    with clean_session_factory() as session:
        forecast_run = _seed_forecast_run(session, values=(Decimal("24100.000"),))
        _seed_quality_state(
            session,
            dataset_name="weather_forecasts",
            severity="error",
            status="failed",
        )

        candidates = evaluate_alert_candidates(
            session,
            production_forecast_run_id=forecast_run.id,
            generated_at_utc=CREATED_AT,
        )

    combined = [item for item in candidates if item.alert_type is AlertType.COMBINED_CONTEXT]
    assert len(combined) == 1
    components = combined[0].evidence["component_alerts"]
    assert isinstance(components, list)
    assert {component["alert_type"] for component in components} == {
        "high_demand",
        "source_health",
    }


@pytest.mark.integration
def test_duplicate_active_alert_prevention(
    clean_session_factory: sessionmaker[Session],
) -> None:
    """Repeated evaluation of the same evidence reuses the active alert."""

    with clean_session_factory() as session:
        forecast_run = _seed_forecast_run(session, values=(Decimal("24100.000"),))

        first = evaluate_and_persist_alerts(
            session,
            production_forecast_run_id=forecast_run.id,
            generated_at_utc=CREATED_AT,
        )
        second = evaluate_and_persist_alerts(
            session,
            production_forecast_run_id=forecast_run.id,
            generated_at_utc=CREATED_AT + timedelta(minutes=5),
        )
        session.commit()

        alerts = list(session.scalars(select(Alert)).all())
        evidence = list(session.scalars(select(AlertEvidence)).all())

    assert first.created_count == 1
    assert second.created_count == 0
    assert second.reused_count == 1
    assert len(alerts) == 1
    assert len(evidence) == 2


@pytest.mark.integration
def test_alert_state_transition_and_invalid_transition(
    clean_session_factory: sessionmaker[Session],
) -> None:
    """Valid lifecycle transitions persist history and invalid transitions are rejected."""

    with clean_session_factory() as session:
        forecast_run = _seed_forecast_run(session, values=(Decimal("24100.000"),))
        evaluate_and_persist_alerts(
            session,
            production_forecast_run_id=forecast_run.id,
            generated_at_utc=CREATED_AT,
        )
        alert = session.scalar(select(Alert))
        assert alert is not None

        transition_alert_state(
            session,
            alert=alert,
            to_state=AlertLifecycleState.ACKNOWLEDGED,
            changed_at_utc=CREATED_AT + timedelta(minutes=1),
            reason="operator reviewed",
        )
        transition_alert_state(
            session,
            alert=alert,
            to_state=AlertLifecycleState.RESOLVED,
            changed_at_utc=CREATED_AT + timedelta(minutes=2),
            reason="condition cleared",
        )
        with pytest.raises(ValueError, match="invalid alert lifecycle transition"):
            transition_alert_state(
                session,
                alert=alert,
                to_state=AlertLifecycleState.OPEN,
                changed_at_utc=CREATED_AT + timedelta(minutes=3),
            )
        session.commit()

        history = list(
            session.scalars(
                select(AlertLifecycleHistory).order_by(AlertLifecycleHistory.changed_at_utc)
            ).all()
        )

    assert alert.state == "resolved"
    assert alert.resolved_at_utc == CREATED_AT + timedelta(minutes=2)
    assert [row.to_state for row in history] == ["open", "acknowledged", "resolved"]


@pytest.mark.integration
def test_alert_evidence_persistence_and_fixed_clock(
    clean_session_factory: sessionmaker[Session],
) -> None:
    """Evaluation stores fixed-clock metadata and structured evidence."""

    with clean_session_factory() as session:
        forecast_run = _seed_forecast_run(session, values=(Decimal("24100.000"),))
        result = evaluate_and_persist_alerts(
            session,
            production_forecast_run_id=forecast_run.id,
            generated_at_utc=CREATED_AT,
        )
        session.commit()

        evaluation_run = session.scalar(select(AlertEvaluationRun))
        evidence = session.scalar(select(AlertEvidence))

    assert result.evaluation_run.started_at_utc == CREATED_AT
    assert evaluation_run is not None
    assert evaluation_run.status == "succeeded"
    assert evaluation_run.completed_at_utc == CREATED_AT
    assert evidence is not None
    assert evidence.generated_at_utc == CREATED_AT
    assert evidence.evidence_json["generated_at_utc"] == CREATED_AT.isoformat()


@pytest.mark.integration
def test_m06_alert_tables_exist_after_metadata_upgrade(
    clean_session_factory: sessionmaker[Session],
    live_postgres_engine: Engine,
) -> None:
    """The M06 alert tables are represented in the database schema."""

    table_names = set(inspect(live_postgres_engine).get_table_names())

    assert {
        "alert_evaluation_runs",
        "alerts",
        "alert_evidence",
        "alert_lifecycle_history",
    }.issubset(table_names)


def _seed_forecast_run(
    session: Session,
    *,
    values: tuple[Decimal, ...],
    forecast_issue_time_utc: datetime = ISSUE_TIME,
) -> ProductionForecastRun:
    run = ProductionForecastRun(
        model_name="alert_test_model",
        model_type="test_model",
        model_version="m06-c01",
        feature_version="m04_c01_foundation",
        forecast_issue_time_utc=forecast_issue_time_utc,
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
            forecast_issue_time_utc=forecast_issue_time_utc,
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


def _seed_ramp_output(
    session: Session,
    forecast_run: ProductionForecastRun,
    *,
    ramp_mw: Decimal,
) -> ForecastRampOutput:
    ramp = ForecastRampOutput(
        production_forecast_run_id=forecast_run.id,
        target_interval_start_utc=ISSUE_TIME + timedelta(hours=2),
        previous_target_interval_start_utc=ISSUE_TIME + timedelta(hours=1),
        forecast_ramp_mw=ramp_mw,
        absolute_ramp_mw=abs(ramp_mw),
        created_at_utc=CREATED_AT,
    )
    session.add(ramp)
    session.flush()
    return ramp


def _seed_quality_state(
    session: Session,
    *,
    dataset_name: str,
    severity: str,
    status: str,
    safe_detail: str | None = None,
) -> None:
    quality_run = QualityRun(
        dataset_name=dataset_name,
        status="succeeded",
        started_at_utc=CREATED_AT,
        completed_at_utc=CREATED_AT,
    )
    session.add(quality_run)
    session.flush()
    result = QualityResult(
        quality_run_id=quality_run.id,
        dataset_name=dataset_name,
        check_name="fixture_source_health_check",
        check_category="freshness",
        severity=severity,
        status=status,
        safe_detail=safe_detail,
        is_blocking=False,
        created_at_utc=CREATED_AT,
    )
    session.add(result)
    session.flush()
