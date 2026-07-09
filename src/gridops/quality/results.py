"""Persistence helpers for M03 quality runs and results."""

import re
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from gridops.models import QualityResult, QualityRun
from gridops.quality.contracts import (
    QualityCheckCategory,
    QualityResultStatus,
    QualityRunStatus,
    QualitySeverity,
    get_dataset_contract,
)

MAX_SAFE_DETAIL_LENGTH = 1000
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


def start_quality_run(
    session: Session,
    *,
    dataset_name: str,
    started_at_utc: datetime | None = None,
    checked_window_start_utc: datetime | None = None,
    checked_window_end_utc: datetime | None = None,
) -> QualityRun:
    """Create and flush a running quality run."""

    get_dataset_contract(dataset_name)
    started_at = _coerce_aware_utc(started_at_utc) if started_at_utc is not None else utc_now()
    window_start = (
        _coerce_aware_utc(checked_window_start_utc)
        if checked_window_start_utc is not None
        else None
    )
    window_end = (
        _coerce_aware_utc(checked_window_end_utc) if checked_window_end_utc is not None else None
    )

    if window_start is not None and window_end is not None and window_start >= window_end:
        raise ValueError("checked window start must be before checked window end")

    run = QualityRun(
        dataset_name=dataset_name,
        status=QualityRunStatus.RUNNING.value,
        started_at_utc=started_at,
        checked_window_start_utc=window_start,
        checked_window_end_utc=window_end,
    )
    session.add(run)
    session.flush()

    return run


def mark_quality_run_succeeded(
    run: QualityRun,
    *,
    completed_at_utc: datetime | None = None,
) -> None:
    """Mark a quality run as successful."""

    run.status = QualityRunStatus.SUCCEEDED.value
    run.completed_at_utc = (
        _coerce_aware_utc(completed_at_utc) if completed_at_utc is not None else utc_now()
    )
    run.safe_error_detail = None


def mark_quality_run_failed(
    run: QualityRun,
    error: Exception | str,
    *,
    completed_at_utc: datetime | None = None,
) -> None:
    """Mark a quality run as failed with bounded safe detail."""

    run.status = QualityRunStatus.FAILED.value
    run.completed_at_utc = (
        _coerce_aware_utc(completed_at_utc) if completed_at_utc is not None else utc_now()
    )
    run.safe_error_detail = _safe_detail(str(error))


def store_quality_result(
    session: Session,
    *,
    quality_run: QualityRun,
    check_name: str,
    check_category: QualityCheckCategory,
    severity: QualitySeverity,
    status: QualityResultStatus,
    observed_value: str | None = None,
    expected_value: str | None = None,
    affected_record_count: int | None = None,
    safe_detail: str | None = None,
    is_blocking: bool = False,
    related_ingestion_run_id: int | None = None,
    related_raw_snapshot_id: int | None = None,
    created_at_utc: datetime | None = None,
) -> QualityResult:
    """Create and flush one quality result for an existing quality run."""

    if affected_record_count is not None and affected_record_count < 0:
        raise ValueError("affected record count cannot be negative")

    result = QualityResult(
        quality_run_id=quality_run.id,
        dataset_name=quality_run.dataset_name,
        check_name=check_name,
        check_category=check_category.value,
        severity=severity.value,
        status=status.value,
        observed_value=observed_value,
        expected_value=expected_value,
        affected_record_count=affected_record_count,
        safe_detail=_safe_detail(safe_detail) if safe_detail is not None else None,
        is_blocking=is_blocking,
        related_ingestion_run_id=related_ingestion_run_id,
        related_raw_snapshot_id=related_raw_snapshot_id,
        created_at_utc=(
            _coerce_aware_utc(created_at_utc) if created_at_utc is not None else utc_now()
        ),
    )
    session.add(result)
    session.flush()

    return result


def _safe_detail(message: str) -> str:
    """Bound and redact detail text before persistence."""

    sanitized = _URL_CREDENTIAL_PATTERN.sub(
        lambda match: f"{match.group('scheme')}{REDACTED}@",
        message,
    )
    sanitized = _KEY_VALUE_SECRET_PATTERN.sub(
        lambda match: f"{match.group(1)}={REDACTED}",
        sanitized,
    )

    return sanitized[:MAX_SAFE_DETAIL_LENGTH]


def _coerce_aware_utc(value: datetime) -> datetime:
    """Return an aware UTC datetime, rejecting naive input."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("quality timestamps must be timezone-aware")

    return value.astimezone(UTC)
