"""Source-health summaries from persisted quality runs and results."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from gridops.models import QualityResult, QualityRun
from gridops.quality.blocking import decide_run_blocking
from gridops.quality.contracts import DATASET_CONTRACTS


@dataclass(frozen=True, slots=True)
class DatasetSourceHealthSummary:
    """Operational source-health view for one dataset."""

    dataset_name: str
    latest_quality_run_status: str
    worst_severity: str | None
    is_blocked: bool
    check_counts_by_status: dict[str, int]
    latest_checked_at_utc: datetime | None
    safe_failure_summaries: tuple[str, ...]


def summarize_source_health(
    session: Session,
) -> list[DatasetSourceHealthSummary]:
    """Summarize persisted source health for every supported dataset."""

    runs = session.scalars(
        select(QualityRun).order_by(
            QualityRun.dataset_name,
            QualityRun.completed_at_utc.desc(),
            QualityRun.started_at_utc.desc(),
            QualityRun.id.desc(),
        )
    ).all()
    latest_run_by_dataset: dict[str, QualityRun] = {}
    for run in runs:
        latest_run_by_dataset.setdefault(run.dataset_name, run)

    results = session.scalars(select(QualityResult).order_by(QualityResult.id)).all()
    results_by_run: dict[int, list[QualityResult]] = {}
    for result in results:
        results_by_run.setdefault(result.quality_run_id, []).append(result)

    summaries: list[DatasetSourceHealthSummary] = []
    for dataset_name in DATASET_CONTRACTS:
        latest_run = latest_run_by_dataset.get(dataset_name)
        if latest_run is None:
            summaries.append(
                DatasetSourceHealthSummary(
                    dataset_name=dataset_name,
                    latest_quality_run_status="not_started",
                    worst_severity=None,
                    is_blocked=False,
                    check_counts_by_status={},
                    latest_checked_at_utc=None,
                    safe_failure_summaries=(),
                )
            )
            continue

        run_results = results_by_run.get(latest_run.id, [])
        decision = decide_run_blocking(latest_run, run_results)
        summaries.append(
            DatasetSourceHealthSummary(
                dataset_name=dataset_name,
                latest_quality_run_status=latest_run.status,
                worst_severity=decision.worst_severity,
                is_blocked=decision.is_blocked,
                check_counts_by_status=_status_counts(run_results),
                latest_checked_at_utc=latest_run.completed_at_utc or latest_run.started_at_utc,
                safe_failure_summaries=_safe_failure_summaries(latest_run, run_results),
            )
        )

    return summaries


def _status_counts(results: list[QualityResult]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    return counts


def _safe_failure_summaries(
    quality_run: QualityRun,
    results: list[QualityResult],
) -> tuple[str, ...]:
    values: list[str] = []
    if quality_run.safe_error_detail:
        values.append(quality_run.safe_error_detail)
    for result in results:
        if result.safe_detail and result.safe_detail not in values:
            values.append(result.safe_detail)
    return tuple(values[:5])
