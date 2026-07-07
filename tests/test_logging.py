"""Tests for structured application logging."""

import json
import logging
from collections.abc import Iterator
from io import StringIO
from typing import Any

import pytest
from pydantic import SecretStr

from gridops.config import LogLevel
from gridops.logging import APP_LOGGER_NAME, REDACTED, configure_logging


@pytest.fixture(autouse=True)
def restore_gridops_logger() -> Iterator[None]:
    """Restore logger state after each test."""

    logger = logging.getLogger(APP_LOGGER_NAME)
    original_handlers = list(logger.handlers)
    original_level = logger.level
    original_disabled = logger.disabled
    original_propagate = logger.propagate

    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    yield

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    for handler in original_handlers:
        logger.addHandler(handler)

    logger.setLevel(original_level)
    logger.disabled = original_disabled
    logger.propagate = original_propagate


def read_single_log_record(stream: StringIO) -> dict[str, Any]:
    """Parse a single JSON log record from a test stream."""

    lines = stream.getvalue().splitlines()

    assert len(lines) == 1

    parsed = json.loads(lines[0])

    assert isinstance(parsed, dict)

    return parsed


def test_configure_logging_is_idempotent() -> None:
    """Repeated configuration leaves exactly one application handler."""

    stream = StringIO()

    first_logger = configure_logging(LogLevel.DEBUG, stream=stream)
    second_logger = configure_logging(LogLevel.INFO, stream=stream)

    assert first_logger is second_logger
    assert second_logger.name == APP_LOGGER_NAME
    assert second_logger.level == logging.INFO
    assert second_logger.propagate is False
    assert len(second_logger.handlers) == 1
    assert second_logger.handlers[0].level == logging.INFO


def test_structured_log_contains_expected_fields() -> None:
    """Application logs are emitted as stable JSON objects."""

    stream = StringIO()
    logger = configure_logging(LogLevel.INFO, stream=stream)

    logger.info(
        "application initialized",
        extra={
            "event": "application_start",
            "attempt": 1,
        },
    )

    payload = read_single_log_record(stream)

    assert payload["level"] == "INFO"
    assert payload["logger"] == APP_LOGGER_NAME
    assert payload["message"] == "application initialized"
    assert payload["event"] == "application_start"
    assert payload["attempt"] == 1
    assert payload["timestamp"].endswith("Z")


def test_structured_logging_redacts_secrets() -> None:
    """Recognized secret fields and credential text are not emitted."""

    stream = StringIO()
    logger = configure_logging(LogLevel.WARNING, stream=stream)

    logger.warning(
        "connection failed password=plain-text "
        "postgresql://visible-user:visible-password@localhost/gridops",
        extra={
            "database_url": ("postgresql://database-user:database-password@localhost/gridops"),
            "context": {
                "token": "context-token",
                "safe_value": "visible",
            },
            "secret_object": SecretStr("secret-object-value"),
        },
    )

    output = stream.getvalue()
    payload = read_single_log_record(stream)

    forbidden_values = (
        "plain-text",
        "visible-user",
        "visible-password",
        "database-user",
        "database-password",
        "context-token",
        "secret-object-value",
    )

    for forbidden_value in forbidden_values:
        assert forbidden_value not in output

    assert REDACTED in payload["message"]
    assert payload["database_url"] == REDACTED
    assert payload["context"]["token"] == REDACTED
    assert payload["context"]["safe_value"] == "visible"
    assert payload["secret_object"] == REDACTED


def test_log_level_filters_lower_severity_messages() -> None:
    """Configured severity controls which records are emitted."""

    stream = StringIO()
    logger = configure_logging(LogLevel.WARNING, stream=stream)

    logger.info("not emitted")
    logger.warning("emitted")

    payload = read_single_log_record(stream)

    assert payload["level"] == "WARNING"
    assert payload["message"] == "emitted"
