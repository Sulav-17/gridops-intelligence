"""FastAPI application foundation for GridOps Intelligence."""

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal, InvalidOperation

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from gridops.config import Settings
from gridops.dashboard import (
    forecast_response,
    latest_forecast_run,
    model_performance_response,
    overview_response,
    system_status_response,
)
from gridops.database import (
    check_database_connection,
    make_engine,
    make_session_factory,
    session_scope,
)
from gridops.decision.alert_engine import evaluate_and_persist_alerts
from gridops.decision.alert_lifecycle import transition_alert_state
from gridops.decision.alert_schemas import AlertLifecycleState
from gridops.decision.briefing_facts import generate_briefing, latest_briefing, utc_now
from gridops.decision.evidence import normalize_evidence
from gridops.decision.scenario_engine import get_scenario, run_scenario
from gridops.decision.scenario_schemas import ScenarioRequest, ScenarioType
from gridops.logging import configure_logging
from gridops.models import (
    Alert,
    AlertEvidence,
    AlertLifecycleHistory,
    BriefingFact,
    BriefingRun,
    ProductionForecastRun,
    ScenarioAssumption,
    ScenarioResultRow,
)
from gridops.quality.source_health import summarize_source_health


class QualityHealthItem(BaseModel):
    """Safe API view of dataset quality health."""

    dataset_name: str
    latest_quality_run_status: str
    worst_severity: str | None
    is_blocked: bool
    check_counts_by_status: dict[str, int]
    latest_checked_at_utc: str | None
    safe_failure_summaries: list[str]


class QualityHealthResponse(BaseModel):
    """Top-level source-health response."""

    datasets: list[QualityHealthItem]


class ScenarioCreateRequest(BaseModel):
    """Request body for deterministic scenario generation."""

    production_forecast_run_id: int
    scenario_type: ScenarioType
    generated_at_utc: str | None = None
    demand_growth_percent: str | None = None
    added_load_mw: str | None = None
    temperature_delta_c: str | None = None
    humidity_delta_percent: str | None = None


class BriefingGenerateRequest(BaseModel):
    """Request body for deterministic briefing generation."""

    production_forecast_run_id: int
    generated_at_utc: str | None = None


class AlertEvaluateRequest(BaseModel):
    """Request body for deterministic alert evaluation."""

    production_forecast_run_id: int
    generated_at_utc: str | None = None


class AlertStateUpdateRequest(BaseModel):
    """Request body for alert lifecycle transitions."""

    state: AlertLifecycleState
    changed_at_utc: str | None = None
    reason: str | None = None


def create_app(
    settings: Settings | None = None,
    *,
    engine: Engine | None = None,
) -> FastAPI:
    """Create the GridOps FastAPI application."""

    resolved_settings = settings if settings is not None else Settings()
    logger = configure_logging(resolved_settings.log_level)
    database_engine = engine if engine is not None else make_engine(resolved_settings)
    owns_engine = engine is None

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if owns_engine:
                database_engine.dispose()

    app = FastAPI(
        title=resolved_settings.app_name,
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.database_engine = database_engine
    app.state.logger = logger
    app.state.session_factory = make_session_factory(database_engine)

    @app.get("/health")
    def health() -> dict[str, str]:
        """Return process health without touching downstream dependencies."""

        return {"status": "ok"}

    @app.get("/ready", response_model=None)
    def ready() -> dict[str, str] | JSONResponse:
        """Return readiness based on real PostgreSQL connectivity."""

        if _database_is_ready(database_engine, logger):
            return {
                "status": "ready",
                "dependency": "postgresql",
            }

        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "dependency": "postgresql",
            },
        )

    @app.get("/quality/health", response_model=QualityHealthResponse)
    def quality_health() -> QualityHealthResponse | JSONResponse:
        """Return safe source-health visibility from persisted quality runs and results."""

        try:
            with session_scope(app.state.session_factory) as session:
                summaries = summarize_source_health(session)
        except Exception as exc:
            logger.warning(
                "Quality health query failed",
                extra={
                    "dependency": "postgresql",
                    "error_type": type(exc).__name__,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "not_ready",
                    "dependency": "postgresql",
                },
            )

        return QualityHealthResponse(
            datasets=[
                QualityHealthItem(
                    dataset_name=summary.dataset_name,
                    latest_quality_run_status=summary.latest_quality_run_status,
                    worst_severity=summary.worst_severity,
                    is_blocked=summary.is_blocked,
                    check_counts_by_status=summary.check_counts_by_status,
                    latest_checked_at_utc=(
                        summary.latest_checked_at_utc.isoformat()
                        if summary.latest_checked_at_utc is not None
                        else None
                    ),
                    safe_failure_summaries=list(summary.safe_failure_summaries),
                )
                for summary in summaries
            ]
        )

    @app.get("/dashboard/overview", response_model=None)
    def dashboard_overview() -> dict[str, object] | JSONResponse:
        """Return the smallest coherent dashboard summary from persisted records."""

        return _database_read_response(app, logger, overview_response, "Dashboard overview")

    @app.get("/forecasts/latest", response_model=None)
    def latest_forecast() -> dict[str, object] | JSONResponse:
        """Return the latest successful persisted production forecast."""

        try:
            with session_scope(app.state.session_factory) as session:
                run = latest_forecast_run(session)
                if run is None:
                    return JSONResponse(
                        status_code=status.HTTP_404_NOT_FOUND,
                        content={"detail": "forecast not found"},
                    )
                body = _json_dict(forecast_response(session, run))
        except Exception as exc:
            return _safe_database_failure(logger, "Latest forecast query", exc)
        return body

    @app.get("/forecasts/{forecast_run_id}", response_model=None)
    def forecast_detail(forecast_run_id: int) -> dict[str, object] | JSONResponse:
        """Return one persisted production forecast and its verifiable outputs."""

        try:
            with session_scope(app.state.session_factory) as session:
                run = session.get(ProductionForecastRun, forecast_run_id)
                if run is None or run.status != "succeeded":
                    return JSONResponse(
                        status_code=status.HTTP_404_NOT_FOUND,
                        content={"detail": "forecast not found"},
                    )
                body = _json_dict(forecast_response(session, run))
        except Exception as exc:
            return _safe_database_failure(logger, "Forecast detail query", exc)
        return body

    @app.get("/model-performance/latest", response_model=None)
    def latest_model_performance() -> dict[str, object] | JSONResponse:
        """Return latest persisted baseline, performance, and drift evidence."""

        return _database_read_response(
            app, logger, model_performance_response, "Model performance query"
        )

    @app.get("/system/status", response_model=None)
    def system_status() -> dict[str, object] | JSONResponse:
        """Return safe dependency state and latest operational timestamps."""

        try:
            with session_scope(app.state.session_factory) as session:
                body = _json_dict(
                    system_status_response(session, demo_mode=resolved_settings.demo_mode)
                )
        except Exception as exc:
            return _safe_database_failure(logger, "System status query", exc)
        return body

    @app.get("/alerts", response_model=None)
    def alerts() -> dict[str, object] | JSONResponse:
        """Return persisted alerts with current evidence."""

        try:
            with session_scope(app.state.session_factory) as session:
                rows = list(session.scalars(select(Alert).order_by(Alert.id)).all())
                body = _json_dict({"alerts": [_alert_summary(alert) for alert in rows]})
        except Exception as exc:
            logger.warning(
                "Alert query failed",
                extra={"error_type": type(exc).__name__},
            )
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not_ready", "dependency": "postgresql"},
            )

        return body

    @app.get("/alerts/{alert_id}", response_model=None)
    def alert_detail(alert_id: int) -> dict[str, object] | JSONResponse:
        """Return one alert with immutable evidence and lifecycle history."""

        try:
            with session_scope(app.state.session_factory) as session:
                alert = session.get(Alert, alert_id)
                if alert is None:
                    return JSONResponse(
                        status_code=status.HTTP_404_NOT_FOUND,
                        content={"detail": "alert not found"},
                    )
                body = _alert_detail_response(session, alert)
        except Exception as exc:
            logger.warning(
                "Alert detail query failed",
                extra={"error_type": type(exc).__name__},
            )
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not_ready", "dependency": "postgresql"},
            )

        return body

    @app.post("/alerts/evaluate", response_model=None)
    def evaluate_alerts(payload: AlertEvaluateRequest) -> dict[str, object] | JSONResponse:
        """Evaluate deterministic alert rules and persist evidence."""

        if resolved_settings.demo_mode:
            return _demo_mode_forbidden()

        try:
            with session_scope(app.state.session_factory) as session:
                result = evaluate_and_persist_alerts(
                    session,
                    production_forecast_run_id=payload.production_forecast_run_id,
                    generated_at_utc=_parse_api_datetime(payload.generated_at_utc),
                )
                body = _json_dict(
                    {
                        "evaluation_run_id": result.evaluation_run.id,
                        "created_count": result.created_count,
                        "reused_count": result.reused_count,
                        "alerts": [_alert_summary(alert) for alert in result.alerts],
                    }
                )
        except ValueError as exc:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": str(exc)},
            )
        except Exception as exc:
            logger.warning(
                "Alert evaluation failed",
                extra={"error_type": type(exc).__name__},
            )
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not_ready", "dependency": "postgresql"},
            )

        return body

    @app.patch("/alerts/{alert_id}/state", response_model=None)
    def update_alert_state(
        alert_id: int,
        payload: AlertStateUpdateRequest,
    ) -> dict[str, object] | JSONResponse:
        """Apply a validated alert lifecycle transition."""

        if resolved_settings.demo_mode:
            return _demo_mode_forbidden()

        try:
            with session_scope(app.state.session_factory) as session:
                alert = session.get(Alert, alert_id)
                if alert is None:
                    return JSONResponse(
                        status_code=status.HTTP_404_NOT_FOUND,
                        content={"detail": "alert not found"},
                    )
                transition_alert_state(
                    session,
                    alert=alert,
                    to_state=payload.state,
                    changed_at_utc=_parse_api_datetime(payload.changed_at_utc),
                    reason=payload.reason,
                )
                body = _alert_detail_response(session, alert)
        except ValueError as exc:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": str(exc)},
            )
        except Exception as exc:
            logger.warning(
                "Alert lifecycle update failed",
                extra={"error_type": type(exc).__name__},
            )
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not_ready", "dependency": "postgresql"},
            )

        return body

    @app.post("/scenarios", response_model=None)
    def create_scenario(payload: ScenarioCreateRequest) -> dict[str, object] | JSONResponse:
        """Generate and persist a deterministic decision-support scenario."""

        try:
            request = ScenarioRequest(
                production_forecast_run_id=payload.production_forecast_run_id,
                scenario_type=payload.scenario_type,
                generated_at_utc=_parse_api_datetime(payload.generated_at_utc),
                demand_growth_percent=_parse_api_decimal(payload.demand_growth_percent),
                added_load_mw=_parse_api_decimal(payload.added_load_mw),
                temperature_delta_c=_parse_api_decimal(payload.temperature_delta_c),
                humidity_delta_percent=_parse_api_decimal(payload.humidity_delta_percent),
            )
            if resolved_settings.demo_mode:
                _validate_demo_scenario(request, resolved_settings)
            with session_scope(app.state.session_factory) as session:
                result = run_scenario(session, request=request)
                body = _scenario_response(session, result.scenario_run.id)
        except ValueError as exc:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)}
            )
        except Exception as exc:
            logger.warning(
                "Scenario generation failed",
                extra={"error_type": type(exc).__name__},
            )
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not_ready", "dependency": "postgresql"},
            )

        return body

    @app.get("/scenarios/{scenario_id}", response_model=None)
    def scenario_detail(scenario_id: int) -> dict[str, object] | JSONResponse:
        """Return persisted scenario assumptions and result rows."""

        try:
            with session_scope(app.state.session_factory) as session:
                scenario = get_scenario(session, scenario_id)
                if scenario is None:
                    return JSONResponse(
                        status_code=status.HTTP_404_NOT_FOUND,
                        content={"detail": "scenario not found"},
                    )
                body = _scenario_response(session, scenario.id)
        except Exception as exc:
            logger.warning(
                "Scenario query failed",
                extra={"error_type": type(exc).__name__},
            )
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not_ready", "dependency": "postgresql"},
            )

        return body

    @app.post("/briefings/generate", response_model=None)
    def generate_briefing_endpoint(
        payload: BriefingGenerateRequest,
    ) -> dict[str, object] | JSONResponse:
        """Generate and persist deterministic briefing facts."""

        if resolved_settings.demo_mode:
            return _demo_mode_forbidden()

        try:
            with session_scope(app.state.session_factory) as session:
                result = generate_briefing(
                    session,
                    production_forecast_run_id=payload.production_forecast_run_id,
                    generated_at_utc=_parse_api_datetime(payload.generated_at_utc),
                )
                body = _briefing_response(session, result.briefing_run.id)
        except ValueError as exc:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)}
            )
        except Exception as exc:
            logger.warning(
                "Briefing generation failed",
                extra={"error_type": type(exc).__name__},
            )
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not_ready", "dependency": "postgresql"},
            )

        return body

    @app.get("/briefings/latest", response_model=None)
    def latest_briefing_endpoint() -> dict[str, object] | JSONResponse:
        """Return the latest persisted deterministic briefing facts."""

        try:
            with session_scope(app.state.session_factory) as session:
                briefing = latest_briefing(session)
                if briefing is None:
                    return JSONResponse(
                        status_code=status.HTTP_404_NOT_FOUND,
                        content={"detail": "briefing not found"},
                    )
                body = _briefing_response(session, briefing.id)
        except Exception as exc:
            logger.warning(
                "Briefing query failed",
                extra={"error_type": type(exc).__name__},
            )
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not_ready", "dependency": "postgresql"},
            )

        return body

    return app


def _database_is_ready(engine: Engine, logger: logging.Logger) -> bool:
    """Check PostgreSQL readiness while keeping response details safe."""

    try:
        return check_database_connection(engine)
    except Exception as exc:
        logger.warning(
            "Readiness check failed",
            extra={
                "dependency": "postgresql",
                "error_type": type(exc).__name__,
            },
        )
        return False


def _parse_api_datetime(value: str | None) -> datetime:
    """Parse an optional aware datetime string for API requests."""

    if value is None:
        return utc_now()
    parsed = value.replace("Z", "+00:00")
    timestamp = datetime.fromisoformat(parsed)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return timestamp


def _parse_api_decimal(value: str | None) -> Decimal | None:
    """Parse an optional Decimal from a string API field."""

    if value is None:
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("scenario values must be valid decimals") from exc
    if not parsed.is_finite():
        raise ValueError("scenario values must be finite")
    return parsed


def _validate_demo_scenario(request: ScenarioRequest, settings: Settings) -> None:
    """Apply configurable public-demo bounds without changing scenario formulas."""

    bounds = (
        (
            "demand_growth_percent",
            request.demand_growth_percent,
            Decimal(str(settings.demo_scenario_load_growth_percent_limit)),
        ),
        (
            "added_load_mw",
            request.added_load_mw,
            Decimal(str(settings.demo_scenario_added_load_mw_limit)),
        ),
        (
            "temperature_delta_c",
            request.temperature_delta_c,
            Decimal(str(settings.demo_scenario_temperature_delta_c_limit)),
        ),
        (
            "humidity_delta_percent",
            request.humidity_delta_percent,
            Decimal(str(settings.demo_scenario_humidity_delta_percent_limit)),
        ),
    )
    for field_name, value, limit in bounds:
        if value is not None and abs(value) > limit:
            raise ValueError(f"{field_name} must be between {-limit} and {limit} in demo mode")


def _demo_mode_forbidden() -> JSONResponse:
    """Return the stable public-demo mutation restriction response."""

    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": "operation unavailable in demo mode"},
    )


def _database_read_response(
    app: FastAPI,
    logger: logging.Logger,
    adapter: Callable[[Session], dict[str, object]],
    operation: str,
) -> dict[str, object] | JSONResponse:
    """Execute a dashboard read adapter with the standard safe database failure shape."""

    try:
        with session_scope(app.state.session_factory) as session:
            body = _json_dict(adapter(session))
    except Exception as exc:
        return _safe_database_failure(logger, operation, exc)
    return body


def _safe_database_failure(
    logger: logging.Logger,
    operation: str,
    exc: Exception,
) -> JSONResponse:
    """Log only an exception type and return no infrastructure detail."""

    logger.warning(operation, extra={"error_type": type(exc).__name__})
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "not_ready", "dependency": "postgresql"},
    )


def _alert_summary(alert: Alert) -> dict[str, object]:
    """Build a JSON-safe alert summary."""

    return {
        "alert_id": alert.id,
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "state": alert.state,
        "fingerprint": alert.fingerprint,
        "rule_name": alert.rule_name,
        "rule_version": alert.rule_version,
        "title": alert.title,
        "explanation": alert.explanation,
        "production_forecast_run_id": alert.production_forecast_run_id,
        "forecast_issue_time_utc": alert.forecast_issue_time_utc,
        "target_interval_start_utc": alert.target_interval_start_utc,
        "target_interval_end_utc": alert.target_interval_end_utc,
        "opened_at_utc": alert.opened_at_utc,
        "updated_at_utc": alert.updated_at_utc,
        "resolved_at_utc": alert.resolved_at_utc,
        "current_evidence": alert.current_evidence_json,
    }


def _alert_detail_response(session: Session, alert: Alert) -> dict[str, object]:
    """Build a JSON-safe alert response with evidence and lifecycle history."""

    evidence_rows = list(
        session.scalars(
            select(AlertEvidence)
            .where(AlertEvidence.alert_id == alert.id)
            .order_by(AlertEvidence.generated_at_utc, AlertEvidence.id)
        ).all()
    )
    lifecycle_rows = list(
        session.scalars(
            select(AlertLifecycleHistory)
            .where(AlertLifecycleHistory.alert_id == alert.id)
            .order_by(AlertLifecycleHistory.changed_at_utc, AlertLifecycleHistory.id)
        ).all()
    )
    return _json_dict(
        {
            **_alert_summary(alert),
            "evidence_records": [
                {
                    "alert_evidence_id": evidence.id,
                    "alert_evaluation_run_id": evidence.alert_evaluation_run_id,
                    "generated_at_utc": evidence.generated_at_utc,
                    "evidence": evidence.evidence_json,
                }
                for evidence in evidence_rows
            ],
            "lifecycle_history": [
                {
                    "lifecycle_history_id": history.id,
                    "from_state": history.from_state,
                    "to_state": history.to_state,
                    "transition_reason": history.transition_reason,
                    "changed_at_utc": history.changed_at_utc,
                }
                for history in lifecycle_rows
            ],
        }
    )


def _scenario_response(session: Session, scenario_id: int) -> dict[str, object]:
    """Build a JSON-safe scenario response."""

    scenario = get_scenario(session, scenario_id)
    if scenario is None:
        raise ValueError("scenario not found")
    assumptions = list(
        session.scalars(
            select(ScenarioAssumption).where(ScenarioAssumption.scenario_run_id == scenario.id)
        ).all()
    )
    rows = list(
        session.scalars(
            select(ScenarioResultRow)
            .where(ScenarioResultRow.scenario_run_id == scenario.id)
            .order_by(ScenarioResultRow.target_interval_start_utc)
        ).all()
    )
    return _json_dict(
        {
            "scenario_id": scenario.id,
            "scenario_type": scenario.scenario_type,
            "production_forecast_run_id": scenario.production_forecast_run_id,
            "status": scenario.status,
            "scenario_version": scenario.scenario_version,
            "generated_at_utc": scenario.generated_at_utc,
            "assumptions": [
                {
                    "assumption_name": assumption.assumption_name,
                    "assumption_value": assumption.assumption_value,
                    "assumption_unit": assumption.assumption_unit,
                    "assumption_json": assumption.assumption_json,
                }
                for assumption in assumptions
            ],
            "limitations": scenario.limitations_json,
            "summary": scenario.summary_json,
            "result_rows": [
                {
                    "target_interval_start_utc": row.target_interval_start_utc,
                    "target_interval_end_utc": row.target_interval_end_utc,
                    "base_value_mw": row.base_value_mw,
                    "scenario_value_mw": row.scenario_value_mw,
                    "delta_mw": row.delta_mw,
                    "row_metadata": row.row_metadata_json,
                }
                for row in rows
            ],
        }
    )


def _briefing_response(session: Session, briefing_id: int) -> dict[str, object]:
    """Build a JSON-safe briefing response."""

    briefing = session.get(BriefingRun, briefing_id)
    if briefing is None:
        raise ValueError("briefing not found")
    facts = list(
        session.scalars(
            select(BriefingFact)
            .where(BriefingFact.briefing_run_id == briefing_id)
            .order_by(BriefingFact.id)
        ).all()
    )
    return _json_dict(
        {
            "briefing_id": briefing.id,
            "production_forecast_run_id": briefing.production_forecast_run_id,
            "status": briefing.status,
            "briefing_version": briefing.briefing_version,
            "generated_at_utc": briefing.generated_at_utc,
            "summary": briefing.summary_json,
            "facts": [
                {
                    "fact_type": fact.fact_type,
                    "fact_value": fact.fact_value_json,
                    "evidence": fact.evidence_json,
                }
                for fact in facts
            ],
        }
    )


def _json_dict(value: dict[str, object]) -> dict[str, object]:
    normalized = normalize_evidence(value)
    if not isinstance(normalized, dict):
        raise ValueError("normalized API response must be a mapping")
    return normalized
