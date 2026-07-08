"""Tests for the FastAPI application foundation."""

from collections.abc import Generator
from typing import cast
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.engine import Engine

from gridops.api import create_app
from gridops.config import AppEnvironment, Settings
from gridops.database import make_engine


@pytest.fixture
def settings() -> Settings:
    """Create API test settings."""

    return Settings(
        app_environment=AppEnvironment.TEST,
        database_url=SecretStr("postgresql+psycopg://gridops:gridops@localhost:55432/gridops_test"),
    )


def test_health_returns_ok_without_database_check(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    """The health endpoint reports process health only."""

    def fail_if_called(_: Engine) -> bool:
        raise AssertionError("health must not touch the database")

    monkeypatch.setattr("gridops.api.check_database_connection", fail_if_called)
    app = create_app(settings, engine=cast(Engine, Mock(spec=Engine)))

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_ready_when_database_check_succeeds(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    """The readiness endpoint succeeds when PostgreSQL connectivity succeeds."""

    monkeypatch.setattr("gridops.api.check_database_connection", lambda _: True)
    app = create_app(settings, engine=cast(Engine, Mock(spec=Engine)))

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dependency": "postgresql",
    }


def test_ready_returns_safe_503_when_database_check_fails(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    """Readiness failures do not leak connection strings or credentials."""

    def fail_check(_: Engine) -> bool:
        raise RuntimeError("postgresql+psycopg://gridops:secret@localhost:55432/gridops_test")

    monkeypatch.setattr("gridops.api.check_database_connection", fail_check)
    app = create_app(settings, engine=cast(Engine, Mock(spec=Engine)))

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "dependency": "postgresql",
    }
    assert "secret" not in response.text
    assert "localhost" not in response.text


@pytest.fixture
def live_postgres_engine() -> Generator[Engine, None, None]:
    """Create an engine for the Docker-backed test database."""

    settings = Settings(
        database_url=SecretStr("postgresql+psycopg://gridops:gridops@localhost:55432/gridops_test")
    )
    engine = make_engine(settings)

    try:
        yield engine
    finally:
        engine.dispose()


@pytest.mark.integration
def test_ready_checks_live_postgres(
    settings: Settings,
    live_postgres_engine: Engine,
) -> None:
    """The readiness endpoint checks real PostgreSQL connectivity."""

    app = create_app(settings, engine=live_postgres_engine)

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dependency": "postgresql",
    }
