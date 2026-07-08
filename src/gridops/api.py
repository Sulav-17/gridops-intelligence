"""FastAPI application foundation for GridOps Intelligence."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from sqlalchemy.engine import Engine

from gridops.config import Settings
from gridops.database import check_database_connection, make_engine
from gridops.logging import configure_logging


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
