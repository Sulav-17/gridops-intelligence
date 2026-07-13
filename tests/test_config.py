"""Tests for application configuration."""

from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from gridops.config import AppEnvironment, LogLevel, Settings

GRIDOPS_ENVIRONMENT_VARIABLES = (
    "GRIDOPS_APP_NAME",
    "GRIDOPS_APP_ENVIRONMENT",
    "GRIDOPS_LOG_LEVEL",
    "GRIDOPS_API_HOST",
    "GRIDOPS_API_PORT",
    "GRIDOPS_DATABASE_URL",
    "GRIDOPS_READINESS_TIMEOUT_SECONDS",
    "GRIDOPS_CORS_ALLOWED_ORIGINS",
    "GRIDOPS_DEMO_MODE",
    "GRIDOPS_DEMO_SCENARIO_LOAD_GROWTH_PERCENT_LIMIT",
    "GRIDOPS_DEMO_SCENARIO_ADDED_LOAD_MW_LIMIT",
    "GRIDOPS_DEMO_SCENARIO_TEMPERATURE_DELTA_C_LIMIT",
    "GRIDOPS_DEMO_SCENARIO_HUMIDITY_DELTA_PERCENT_LIMIT",
)


@pytest.fixture(autouse=True)
def isolate_configuration_sources(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Prevent local files and host variables from affecting tests."""

    monkeypatch.chdir(tmp_path)

    for variable_name in GRIDOPS_ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(variable_name, raising=False)


def test_settings_defaults() -> None:
    """Documented defaults produce a valid local configuration."""

    settings = Settings()

    assert settings.app_name == "GridOps Intelligence"
    assert settings.app_environment is AppEnvironment.LOCAL
    assert settings.log_level is LogLevel.INFO
    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 8000
    assert settings.readiness_timeout_seconds == 2.0
    assert settings.cors_allowed_origins == ("http://localhost:3000", "http://127.0.0.1:3000")
    assert settings.demo_mode is False
    assert settings.demo_scenario_load_growth_percent_limit == 10.0
    assert settings.demo_scenario_added_load_mw_limit == 2000.0
    assert settings.demo_scenario_temperature_delta_c_limit == 10.0
    assert settings.demo_scenario_humidity_delta_percent_limit == 30.0
    assert (
        settings.database_url.get_secret_value()
        == "postgresql+psycopg://gridops:gridops@localhost:55432/gridops"
    )


def test_environment_variables_override_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GRIDOPS-prefixed environment variables override defaults."""

    monkeypatch.setenv("GRIDOPS_APP_NAME", "GridOps Test")
    monkeypatch.setenv("GRIDOPS_APP_ENVIRONMENT", "test")
    monkeypatch.setenv("GRIDOPS_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("GRIDOPS_API_HOST", "0.0.0.0")
    monkeypatch.setenv("GRIDOPS_API_PORT", "9000")
    monkeypatch.setenv(
        "GRIDOPS_DATABASE_URL",
        "postgresql+psycopg://test-user:test-password@localhost:55432/test-gridops",
    )
    monkeypatch.setenv("GRIDOPS_READINESS_TIMEOUT_SECONDS", "5.5")
    monkeypatch.setenv("GRIDOPS_DEMO_MODE", "true")
    monkeypatch.setenv(
        "GRIDOPS_CORS_ALLOWED_ORIGINS", "https://dashboard.example, https://preview.example"
    )

    settings = Settings()

    assert settings.app_name == "GridOps Test"
    assert settings.app_environment is AppEnvironment.TEST
    assert settings.log_level is LogLevel.DEBUG
    assert settings.api_host == "0.0.0.0"
    assert settings.api_port == 9000
    assert settings.readiness_timeout_seconds == 5.5
    assert settings.demo_mode is True
    assert settings.cors_allowed_origins == ("https://dashboard.example", "https://preview.example")
    assert (
        settings.database_url.get_secret_value()
        == "postgresql+psycopg://test-user:test-password@localhost:55432/test-gridops"
    )


@pytest.mark.parametrize(
    ("environment_variable", "value"),
    [
        ("GRIDOPS_APP_ENVIRONMENT", "invalid"),
        ("GRIDOPS_LOG_LEVEL", "TRACE"),
        ("GRIDOPS_API_PORT", "0"),
        ("GRIDOPS_API_PORT", "70000"),
        ("GRIDOPS_READINESS_TIMEOUT_SECONDS", "0"),
        ("GRIDOPS_DATABASE_URL", "sqlite:///gridops.db"),
    ],
)
def test_invalid_configuration_fails_clearly(
    monkeypatch: pytest.MonkeyPatch,
    environment_variable: str,
    value: str,
) -> None:
    """Invalid values produce a configuration validation error."""

    monkeypatch.setenv(environment_variable, value)

    with pytest.raises(ValidationError):
        Settings()


def test_database_url_is_hidden_from_representation() -> None:
    """Configuration representations do not reveal database credentials."""

    database_url = SecretStr(
        "postgresql+psycopg://sensitive-user:sensitive-password@localhost:55432/gridops"
    )

    settings = Settings(database_url=database_url)
    representation = repr(settings)
    serialized = str(settings)

    assert "sensitive-user" not in representation
    assert "sensitive-password" not in representation
    assert "sensitive-user" not in serialized
    assert "sensitive-password" not in serialized
    assert "**********" in representation


def test_production_configuration_rejects_cors_wildcard() -> None:
    """Production browser access must use explicit origins."""

    with pytest.raises(ValidationError, match="cors_allowed_origins"):
        Settings(
            app_environment=AppEnvironment.PRODUCTION,
            cors_allowed_origins=("*",),
        )
