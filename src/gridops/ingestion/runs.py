"""Ingestion run bookkeeping helpers."""

import re
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from gridops.models import IngestionRun
from gridops.sources import SourceDefinition

MAX_ERROR_MESSAGE_LENGTH = 1000
REDACTED = "[REDACTED]"
_URL_CREDENTIAL_PATTERN = re.compile(
    r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)"
    r"(?:[^/\s:@]+):(?:[^@/\s]+)@"
)
_KEY_VALUE_SECRET_PATTERN = re.compile(
    r"\b(password|passwd|secret|token|api[_-]?key|credential)"
    r"\s*[:=]\s*([^\s,;]+)",
    flags=re.IGNORECASE,
)


def utc_now() -> datetime:
    """Return the current aware UTC timestamp."""

    return datetime.now(UTC)


def start_ingestion_run(
    session: Session,
    *,
    source: SourceDefinition,
    mode: str,
    started_at_utc: datetime | None = None,
) -> IngestionRun:
    """Create and flush a running ingestion run record."""

    run = IngestionRun(
        source_name=source.name,
        source_type=source.source_type,
        mode=mode,
        parser_version=source.parser_version,
        status="running",
        started_at_utc=started_at_utc if started_at_utc is not None else utc_now(),
        records_seen=0,
        records_loaded=0,
    )
    session.add(run)
    session.flush()

    return run


def mark_ingestion_run_succeeded(
    run: IngestionRun,
    *,
    records_seen: int,
    records_loaded: int,
    finished_at_utc: datetime | None = None,
) -> None:
    """Mark an ingestion run as successful."""

    run.status = "succeeded"
    run.finished_at_utc = finished_at_utc if finished_at_utc is not None else utc_now()
    run.records_seen = records_seen
    run.records_loaded = records_loaded
    run.error_type = None
    run.error_message = None


def mark_ingestion_run_failed(
    run: IngestionRun,
    exc: Exception,
    *,
    finished_at_utc: datetime | None = None,
) -> None:
    """Mark an ingestion run as failed with bounded safe detail."""

    run.status = "failed"
    run.finished_at_utc = finished_at_utc if finished_at_utc is not None else utc_now()
    run.error_type = type(exc).__name__
    run.error_message = _safe_error_message(str(exc))


def _safe_error_message(message: str) -> str:
    """Bound failure text so database rows cannot grow without limit."""

    sanitized = _URL_CREDENTIAL_PATTERN.sub(
        lambda match: f"{match.group('scheme')}{REDACTED}@",
        message,
    )
    sanitized = _KEY_VALUE_SECRET_PATTERN.sub(
        lambda match: f"{match.group(1)}={REDACTED}",
        sanitized,
    )

    return sanitized[:MAX_ERROR_MESSAGE_LENGTH]
