"""Application configuration for GridOps Intelligence."""

from enum import StrEnum

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
        "postgresql+psycopg://gridops:gridops@localhost:5432/gridops"
    )
    readiness_timeout_seconds: float = Field(default=2.0, gt=0, le=30)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        """Require an explicit PostgreSQL connection URL."""

        raw_value = value.get_secret_value()

        if not raw_value.startswith(("postgresql://", "postgresql+")):
            raise ValueError("database_url must use a PostgreSQL scheme")

        return value
