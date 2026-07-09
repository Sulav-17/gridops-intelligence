"""Blocking decisions based on persisted quality runs and results."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from gridops.models import QualityResult, QualityRun
from gridops.quality.contracts import QualitySeverity

_SEVERITY_RANK = {
    QualitySeverity.INFO.value: 0,
    QualitySeverity.WARNING.value: 1,
    QualitySeverity.ERROR.value: 2,
    QualitySeverity.CRITICAL.value: 3,
}


@dataclass(frozen=True, slots=True)
class BlockingDecision:
    """Whether a dataset and optional checked window can be used downstream."""

    dataset_name: str
    checked_window_start_utc: datetime | None
    checked_window_end_utc: datetime | None
    quality_run_id: int | None
    quality_run_status: str | None
    is_blocked: bool
    worst_severity: str | None
    blocking_result_count: int
    blocking_reasons: tuple[str, ...]


def get_blocking_decision(
    session: Session,
    *,
    dataset_name: str,
    checked_window_start_utc: datetime | None = None,
    checked_window_end_utc: datetime | None = None,
) -> BlockingDecision:
    """Return the blocking decision for the latest applicable persisted quality run."""

    latest_run = _latest_applicable_run(
        session,
        dataset_name=dataset_name,
        checked_window_start_utc=checked_window_start_utc,
        checked_window_end_utc=checked_window_end_utc,
    )
    if latest_run is None:
        return BlockingDecision(
            dataset_name=dataset_name,
            checked_window_start_utc=checked_window_start_utc,
            checked_window_end_utc=checked_window_end_utc,
            quality_run_id=None,
            quality_run_status=None,
            is_blocked=False,
            worst_severity=None,
            blocking_result_count=0,
            blocking_reasons=(),
        )

    results = list(
        session.scalars(
            select(QualityResult)
            .where(QualityResult.quality_run_id == latest_run.id)
            .order_by(QualityResult.id)
        ).all()
    )
    return decide_run_blocking(latest_run, results)


def decide_run_blocking(
    quality_run: QualityRun,
    results: list[QualityResult],
) -> BlockingDecision:
    """Apply M03 blocking rules to one persisted quality run and its results."""

    blocking_reasons: list[str] = []
    blocked = False
    worst_severity: str | None = None

    for result in results:
        worst_severity = _max_severity(worst_severity, result.severity)
        if result.is_blocking:
            blocked = True
            blocking_reasons.append(f"{result.check_name}: explicit blocking flag")
            continue
        if result.severity == QualitySeverity.ERROR.value:
            blocked = True
            blocking_reasons.append(f"{result.check_name}: error severity")
        elif result.severity == QualitySeverity.CRITICAL.value:
            blocked = True
            blocking_reasons.append(f"{result.check_name}: critical severity")

    if quality_run.status == "failed":
        blocked = True
        worst_severity = _max_severity(worst_severity, QualitySeverity.CRITICAL.value)
        blocking_reasons.append("quality run failed")

    return BlockingDecision(
        dataset_name=quality_run.dataset_name,
        checked_window_start_utc=quality_run.checked_window_start_utc,
        checked_window_end_utc=quality_run.checked_window_end_utc,
        quality_run_id=quality_run.id,
        quality_run_status=quality_run.status,
        is_blocked=blocked,
        worst_severity=worst_severity,
        blocking_result_count=len(blocking_reasons),
        blocking_reasons=tuple(blocking_reasons),
    )


def _latest_applicable_run(
    session: Session,
    *,
    dataset_name: str,
    checked_window_start_utc: datetime | None,
    checked_window_end_utc: datetime | None,
) -> QualityRun | None:
    runs = session.scalars(
        select(QualityRun)
        .where(QualityRun.dataset_name == dataset_name)
        .order_by(
            QualityRun.completed_at_utc.desc(),
            QualityRun.started_at_utc.desc(),
            QualityRun.id.desc(),
        )
    ).all()
    applicable = [
        run
        for run in runs
        if _window_overlaps(
            run.checked_window_start_utc,
            run.checked_window_end_utc,
            checked_window_start_utc,
            checked_window_end_utc,
        )
    ]
    return applicable[0] if applicable else None


def _window_overlaps(
    run_start: datetime | None,
    run_end: datetime | None,
    request_start: datetime | None,
    request_end: datetime | None,
) -> bool:
    if request_start is None and request_end is None:
        return True
    if run_start is None and run_end is None:
        return True

    effective_run_start = run_start if run_start is not None else datetime(1970, 1, 1, tzinfo=UTC)
    effective_run_end = (
        run_end if run_end is not None else datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=UTC)
    )
    effective_request_start = (
        request_start if request_start is not None else datetime(1970, 1, 1, tzinfo=UTC)
    )
    effective_request_end = (
        request_end
        if request_end is not None
        else datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=UTC)
    )
    return (
        effective_run_start < effective_request_end and effective_request_start < effective_run_end
    )


def _max_severity(left: str | None, right: str | None) -> str | None:
    if right is None:
        return left
    if left is None:
        return right
    if _SEVERITY_RANK[right] > _SEVERITY_RANK[left]:
        return right
    return left
