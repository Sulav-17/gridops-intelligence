"""FastAPI application foundation for GridOps Intelligence."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.engine import Engine

from gridops.config import Settings
from gridops.database import (
    check_database_connection,
    make_engine,
    make_session_factory,
    session_scope,
)
from gridops.logging import configure_logging
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
