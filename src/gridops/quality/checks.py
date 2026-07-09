"""Reusable quality check result utilities."""

from dataclasses import dataclass

from gridops.quality.contracts import QualityCheckCategory, QualityResultStatus, QualitySeverity
from gridops.quality.results import MAX_SAFE_DETAIL_LENGTH


@dataclass(frozen=True, slots=True)
class QualityCheckResult:
    """In-memory quality result compatible with persistence helpers."""

    dataset_name: str
    check_name: str
    check_category: QualityCheckCategory
    severity: QualitySeverity
    status: QualityResultStatus
    observed_value: str | None = None
    expected_value: str | None = None
    affected_record_count: int | None = None
    safe_detail: str | None = None
    is_blocking: bool = False


def passed_result(
    *,
    dataset_name: str,
    check_name: str,
    check_category: QualityCheckCategory,
    severity: QualitySeverity = QualitySeverity.INFO,
    observed_value: str | None = None,
    expected_value: str | None = None,
    affected_record_count: int | None = 0,
    safe_detail: str | None = None,
) -> QualityCheckResult:
    """Build a passing in-memory quality result."""

    return QualityCheckResult(
        dataset_name=dataset_name,
        check_name=check_name,
        check_category=check_category,
        severity=severity,
        status=QualityResultStatus.PASSED,
        observed_value=observed_value,
        expected_value=expected_value,
        affected_record_count=affected_record_count,
        safe_detail=_bound_safe_detail(safe_detail),
        is_blocking=False,
    )


def failed_result(
    *,
    dataset_name: str,
    check_name: str,
    check_category: QualityCheckCategory,
    severity: QualitySeverity = QualitySeverity.ERROR,
    observed_value: str | None = None,
    expected_value: str | None = None,
    affected_record_count: int | None = None,
    safe_detail: str | None = None,
    is_blocking: bool = True,
) -> QualityCheckResult:
    """Build a failing in-memory quality result."""

    return QualityCheckResult(
        dataset_name=dataset_name,
        check_name=check_name,
        check_category=check_category,
        severity=severity,
        status=QualityResultStatus.FAILED,
        observed_value=observed_value,
        expected_value=expected_value,
        affected_record_count=affected_record_count,
        safe_detail=_bound_safe_detail(safe_detail),
        is_blocking=is_blocking,
    )


def skipped_result(
    *,
    dataset_name: str,
    check_name: str,
    check_category: QualityCheckCategory,
    severity: QualitySeverity = QualitySeverity.WARNING,
    observed_value: str | None = None,
    expected_value: str | None = None,
    safe_detail: str | None = None,
) -> QualityCheckResult:
    """Build a skipped in-memory quality result for known unsupported cases."""

    return QualityCheckResult(
        dataset_name=dataset_name,
        check_name=check_name,
        check_category=check_category,
        severity=severity,
        status=QualityResultStatus.SKIPPED,
        observed_value=observed_value,
        expected_value=expected_value,
        affected_record_count=0,
        safe_detail=_bound_safe_detail(safe_detail),
        is_blocking=False,
    )


def _bound_safe_detail(value: str | None) -> str | None:
    if value is None:
        return None

    return value[:MAX_SAFE_DETAIL_LENGTH]
