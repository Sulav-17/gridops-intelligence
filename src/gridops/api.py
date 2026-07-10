"""FastAPI application foundation for GridOps Intelligence."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from gridops.config import Settings
from gridops.database import (
    check_database_connection,
    make_engine,
    make_session_factory,
    session_scope,
)
from gridops.decision.briefing_facts import generate_briefing, latest_briefing, utc_now
from gridops.decision.evidence import normalize_evidence
from gridops.decision.scenario_engine import get_scenario, run_scenario
from gridops.decision.scenario_schemas import ScenarioRequest, ScenarioType
from gridops.logging import configure_logging
from gridops.models import BriefingFact, BriefingRun, ScenarioAssumption, ScenarioResultRow
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
    return Decimal(value)


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
