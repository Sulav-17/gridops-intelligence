"""Structured logging for GridOps Intelligence."""

import json
import logging
import re
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, TextIO

from pydantic import SecretStr

from gridops.config import LogLevel

APP_LOGGER_NAME = "gridops"
REDACTED = "[REDACTED]"

_STANDARD_LOG_RECORD_FIELDS = frozenset(
    logging.LogRecord(
        name="",
        level=0,
        pathname="",
        lineno=0,
        msg="",
        args=(),
        exc_info=None,
    ).__dict__
) | {"message", "asctime"}

_SENSITIVE_FIELD_NAMES = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "connection_string",
        "credential",
        "credentials",
        "database_url",
        "dsn",
        "password",
        "passwd",
        "secret",
        "token",
    }
)

_URL_CREDENTIAL_PATTERN = re.compile(
    r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)"
    r"(?:[^/\s:@]+):(?:[^@/\s]+)@"
)

_KEY_VALUE_SECRET_PATTERN = re.compile(
    r"\b(password|passwd|secret|token|api[_-]?key|credential)"
    r"\s*[:=]\s*([^\s,;]+)",
    flags=re.IGNORECASE,
)


def _is_sensitive_field(field_name: str) -> bool:
    """Return whether a structured field should always be redacted."""

    normalized = field_name.strip().lower().replace("-", "_")
    return normalized in _SENSITIVE_FIELD_NAMES


def _sanitize_text(value: str) -> str:
    """Remove common credential forms from unstructured text."""

    sanitized = _URL_CREDENTIAL_PATTERN.sub(
        lambda match: f"{match.group('scheme')}{REDACTED}@",
        value,
    )

    return _KEY_VALUE_SECRET_PATTERN.sub(
        lambda match: f"{match.group(1)}={REDACTED}",
        sanitized,
    )


def _redact_value(field_name: str, value: Any) -> Any:
    """Convert a value into JSON-safe data while removing secrets."""

    if _is_sensitive_field(field_name):
        return REDACTED

    if isinstance(value, SecretStr):
        return REDACTED

    if isinstance(value, Mapping):
        return {
            str(key): _redact_value(str(key), nested_value) for key, nested_value in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [_redact_value(field_name, item) for item in value]

    if isinstance(value, str):
        return _sanitize_text(value)

    if value is None or isinstance(value, (bool, int, float)):
        return value

    return _sanitize_text(str(value))


class JsonFormatter(logging.Formatter):
    """Render application log records as one-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record without exposing recognized secrets."""

        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=UTC,
            )
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": _sanitize_text(record.getMessage()),
        }

        for field_name, value in record.__dict__.items():
            if field_name not in _STANDARD_LOG_RECORD_FIELDS and not field_name.startswith("_"):
                payload[field_name] = _redact_value(field_name, value)

        if record.exc_info is not None:
            payload["exception"] = _sanitize_text(self.formatException(record.exc_info))

        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )


def configure_logging(
    log_level: LogLevel,
    *,
    stream: TextIO | None = None,
) -> logging.Logger:
    """Configure the GridOps application logger consistently."""

    logger = logging.getLogger(APP_LOGGER_NAME)

    for existing_handler in list(logger.handlers):
        logger.removeHandler(existing_handler)
        existing_handler.close()

    output_stream = stream if stream is not None else sys.stdout

    handler = logging.StreamHandler(output_stream)
    handler.setLevel(log_level.value)
    handler.setFormatter(JsonFormatter())

    logger.setLevel(log_level.value)
    logger.disabled = False
    logger.propagate = False
    logger.addHandler(handler)

    return logger
