"""Tests for persisted quality blocking decisions."""

from datetime import UTC, datetime

from gridops.models import QualityResult, QualityRun
from gridops.quality.blocking import decide_run_blocking


def test_blocking_allows_info_and_warning_by_default() -> None:
    run = _run()
    results = [
        _result(check_name="row_count", severity="info"),
        _result(check_name="freshness", severity="warning"),
    ]

    decision = decide_run_blocking(run, results)

    assert decision.is_blocked is False
    assert decision.worst_severity == "warning"
    assert decision.blocking_result_count == 0


def test_blocking_error_severity_blocks_dataset_window() -> None:
    run = _run()
    decision = decide_run_blocking(
        run,
        [_result(check_name="continuity", severity="error")],
    )

    assert decision.is_blocked is True
    assert decision.worst_severity == "error"
    assert "error severity" in decision.blocking_reasons[0]


def test_blocking_critical_severity_and_explicit_flag_both_block() -> None:
    run = _run()
    decision = decide_run_blocking(
        run,
        [
            _result(check_name="schema", severity="critical"),
            _result(check_name="metadata", severity="warning", is_blocking=True),
        ],
    )

    assert decision.is_blocked is True
    assert decision.worst_severity == "critical"
    assert decision.blocking_result_count == 2


def test_failed_quality_run_blocks_even_without_results() -> None:
    run = _run(status="failed")

    decision = decide_run_blocking(run, [])

    assert decision.is_blocked is True
    assert decision.worst_severity == "critical"
    assert decision.blocking_reasons == ("quality run failed",)


def _run(*, status: str = "succeeded") -> QualityRun:
    return QualityRun(
        id=1,
        dataset_name="ieso_hourly_demand",
        status=status,
        started_at_utc=datetime(2026, 7, 9, 12, tzinfo=UTC),
        completed_at_utc=datetime(2026, 7, 9, 12, 5, tzinfo=UTC),
        checked_window_start_utc=datetime(2026, 1, 1, tzinfo=UTC),
        checked_window_end_utc=datetime(2026, 1, 2, tzinfo=UTC),
    )


def _result(
    *,
    check_name: str,
    severity: str,
    is_blocking: bool = False,
) -> QualityResult:
    return QualityResult(
        id=1,
        quality_run_id=1,
        dataset_name="ieso_hourly_demand",
        check_name=check_name,
        check_category="schema",
        severity=severity,
        status="failed" if severity in {"error", "critical"} or is_blocking else "passed",
        is_blocking=is_blocking,
        created_at_utc=datetime(2026, 7, 9, 12, tzinfo=UTC),
    )
