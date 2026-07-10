"""Model-selection gate logic for M05."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from gridops.forecasting.model_contracts import ModelSelectionStatus
from gridops.models import ModelSelectionResult

MAE = "mae"
WAPE = "wape"
REQUIRED_LINEAGE_FIELDS = (
    "model_name",
    "model_version",
    "feature_version",
    "training_window_start_utc",
    "training_window_end_utc",
    "evaluation_window_start_utc",
    "evaluation_window_end_utc",
)


@dataclass(frozen=True, slots=True)
class SelectionGateDecision:
    """Decision from evaluating a candidate against a selected baseline."""

    selection_status: ModelSelectionStatus
    selected: bool
    reason: str


def evaluate_model_selection_gate(
    *,
    candidate_metrics: dict[str, object],
    baseline_metrics: dict[str, object],
    selected_baseline_name: str,
    lineage_metadata: dict[str, object],
) -> SelectionGateDecision:
    """Evaluate the default M05 model-selection gate."""

    missing_lineage = [
        field_name for field_name in REQUIRED_LINEAGE_FIELDS if not lineage_metadata.get(field_name)
    ]
    if missing_lineage:
        return _rejected(f"missing required lineage fields: {', '.join(missing_lineage)}")

    if _has_slice_sanity_failure(candidate_metrics):
        return _rejected("candidate has slice sanity failure")

    baseline_metric_values = _selected_baseline_metrics(
        baseline_metrics,
        selected_baseline_name=selected_baseline_name,
    )
    candidate_mae = _metric_decimal(candidate_metrics, MAE)
    baseline_mae = _metric_decimal(baseline_metric_values, MAE)
    if candidate_mae is None or baseline_mae is None:
        return _rejected("candidate and selected baseline MAE are required")
    if candidate_mae > baseline_mae:
        return _rejected(f"candidate MAE {candidate_mae} exceeds baseline MAE {baseline_mae}")

    candidate_wape = _metric_decimal(candidate_metrics, WAPE)
    baseline_wape = _metric_decimal(baseline_metric_values, WAPE)
    if candidate_wape is not None and baseline_wape is not None and candidate_wape > baseline_wape:
        return _rejected(f"candidate WAPE {candidate_wape} exceeds baseline WAPE {baseline_wape}")

    return SelectionGateDecision(
        selection_status=ModelSelectionStatus.SELECTED,
        selected=True,
        reason=f"candidate satisfies selection gate against {selected_baseline_name}",
    )


def persist_model_selection_result(
    session: Session,
    *,
    decision: SelectionGateDecision,
    model_name: str,
    model_type: str,
    model_version: str,
    feature_version: str,
    candidate_metrics: dict[str, object],
    baseline_metrics: dict[str, object],
    training_window_start_utc: datetime,
    training_window_end_utc: datetime,
    evaluation_window_start_utc: datetime,
    evaluation_window_end_utc: datetime,
    model_training_run_id: int | None = None,
    model_artifact_id: int | None = None,
    lineage_metadata: dict[str, object] | None = None,
    created_at_utc: datetime | None = None,
) -> ModelSelectionResult:
    """Persist a model-selection gate decision."""

    result = ModelSelectionResult(
        model_training_run_id=model_training_run_id,
        model_artifact_id=model_artifact_id,
        model_name=model_name,
        model_type=model_type,
        model_version=model_version,
        feature_version=feature_version,
        selection_status=decision.selection_status.value,
        selection_reason=decision.reason,
        training_window_start_utc=_coerce_aware_utc(training_window_start_utc),
        training_window_end_utc=_coerce_aware_utc(training_window_end_utc),
        evaluation_window_start_utc=_coerce_aware_utc(evaluation_window_start_utc),
        evaluation_window_end_utc=_coerce_aware_utc(evaluation_window_end_utc),
        candidate_metrics_json=candidate_metrics,
        baseline_metrics_json=baseline_metrics,
        lineage_metadata=lineage_metadata,
        created_at_utc=(
            _coerce_aware_utc(created_at_utc) if created_at_utc is not None else utc_now()
        ),
    )
    session.add(result)
    session.flush()

    return result


def utc_now() -> datetime:
    """Return the current aware UTC timestamp."""

    return datetime.now(UTC)


def _rejected(reason: str) -> SelectionGateDecision:
    return SelectionGateDecision(
        selection_status=ModelSelectionStatus.REJECTED,
        selected=False,
        reason=reason,
    )


def _selected_baseline_metrics(
    baseline_metrics: dict[str, object],
    *,
    selected_baseline_name: str,
) -> dict[str, object]:
    selected_metrics = baseline_metrics.get(selected_baseline_name)
    if isinstance(selected_metrics, dict):
        return selected_metrics

    return baseline_metrics


def _metric_decimal(metrics: dict[str, object], metric_name: str) -> Decimal | None:
    value = metrics.get(metric_name)
    if value is None:
        return None

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _has_slice_sanity_failure(candidate_metrics: dict[str, object]) -> bool:
    if candidate_metrics.get("slice_sanity_failed") is True:
        return True

    failures = candidate_metrics.get("slice_sanity_failures")
    return isinstance(failures, list) and len(failures) > 0


def _coerce_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("model-selection timestamps must be timezone-aware")

    return value.astimezone(UTC)
