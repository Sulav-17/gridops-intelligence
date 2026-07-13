"""Application configuration for GridOps Intelligence."""

from enum import StrEnum
from typing import Annotated

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class AppEnvironment(StrEnum):
    """Supported application environments."""

    LOCAL = "local"
    TEST = "test"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    """Supported application log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """Strongly typed application settings loaded from the environment."""

    model_config = SettingsConfigDict(
        env_prefix="GRIDOPS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="GridOps Intelligence", min_length=1)
    app_environment: AppEnvironment = AppEnvironment.LOCAL
    log_level: LogLevel = LogLevel.INFO
    api_host: str = Field(default="127.0.0.1", min_length=1)
    api_port: int = Field(default=8000, ge=1, le=65535)
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://gridops:gridops@localhost:55432/gridops"
    )
    readiness_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    cors_allowed_origins: Annotated[tuple[str, ...], NoDecode] = (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    )
    demo_mode: bool = False
    demo_scenario_load_growth_percent_limit: float = Field(default=10.0, gt=0, le=100)
    demo_scenario_added_load_mw_limit: float = Field(default=2000.0, gt=0)
    demo_scenario_temperature_delta_c_limit: float = Field(default=10.0, gt=0, le=50)
    demo_scenario_humidity_delta_percent_limit: float = Field(default=30.0, gt=0, le=100)

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_allowed_origins(cls, value: object) -> object:
        """Accept a comma-separated deployment environment value for CORS origins."""

        if isinstance(value, str):
            return tuple(origin.strip() for origin in value.split(",") if origin.strip())
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        """Require an explicit PostgreSQL connection URL."""

        raw_value = value.get_secret_value()

        if not raw_value.startswith(("postgresql://", "postgresql+")):
            raise ValueError("database_url must use a PostgreSQL scheme")

        return value

    @model_validator(mode="after")
    def reject_production_cors_wildcard(self) -> "Settings":
        """Keep public browser access explicitly origin-scoped in production."""

        if self.app_environment is AppEnvironment.PRODUCTION and "*" in self.cors_allowed_origins:
            raise ValueError("cors_allowed_origins cannot contain '*' in production")
        return self
