"""Candidate training pipeline for M05."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from gridops.forecasting.artifacts import persist_model_artifact_metadata, save_artifact
from gridops.forecasting.baselines import BaselinePrediction
from gridops.forecasting.candidate_models import (
    FEATURE_NAMES,
    CandidateRegressor,
    feature_vector_from_payload,
    make_gradient_boosting_candidate,
    parse_feature_payload,
    payload_uses_no_target_actuals,
)
from gridops.forecasting.metrics import calculate_baseline_metrics
from gridops.forecasting.model_contracts import (
    ModelArtifactStatus,
    ModelTrainingStatus,
)
from gridops.forecasting.model_selection import (
    evaluate_model_selection_gate,
    persist_model_selection_result,
)
from gridops.models import (
    BaselineForecastRun,
    BaselineMetricResult,
    FeatureSnapshotRow,
    IesoHourlyDemand,
    ModelArtifact,
    ModelSelectionResult,
    ModelTrainingRun,
)

DEFAULT_CANDIDATE_MODEL_NAME = "gradient_boosting_candidate"
DEFAULT_CANDIDATE_MODEL_TYPE = "sklearn_gradient_boosting_regressor"
DEFAULT_CANDIDATE_MODEL_VERSION = "m05_c03_candidate_v1"
TIME_BASED_SPLIT = "time_window"
MINIMUM_TRAINING_ROWS = 2
MINIMUM_EVALUATION_ROWS = 1


@dataclass(frozen=True, slots=True)
class CandidateTrainingConfig:
    """Configuration for one deterministic candidate training run."""

    feature_version: str
    training_window_start_utc: datetime
    training_window_end_utc: datetime
    evaluation_window_start_utc: datetime
    evaluation_window_end_utc: datetime
    selected_baseline_name: str
    model_name: str = DEFAULT_CANDIDATE_MODEL_NAME
    model_type: str = DEFAULT_CANDIDATE_MODEL_TYPE
    model_version: str = DEFAULT_CANDIDATE_MODEL_VERSION
    split_strategy: str = TIME_BASED_SPLIT
    random_state: int = 42
    artifact_dir: Path | str | None = None
    created_at_utc: datetime | None = None

    def __post_init__(self) -> None:
        if self.split_strategy != TIME_BASED_SPLIT:
            raise ValueError("candidate training only supports time_window split_strategy")
        _validate_window(
            self.training_window_start_utc,
            self.training_window_end_utc,
            "training window",
        )
        _validate_window(
            self.evaluation_window_start_utc,
            self.evaluation_window_end_utc,
            "evaluation window",
        )
        if not self.feature_version:
            raise ValueError("feature_version must be non-empty")
        if not self.selected_baseline_name:
            raise ValueError("selected_baseline_name must be non-empty")


@dataclass(frozen=True, slots=True)
class CandidateTrainingResult:
    """Persisted outputs from one candidate training attempt."""

    training_run: ModelTrainingRun
    artifact: ModelArtifact | None
    selection_result: ModelSelectionResult | None
    candidate_metrics: dict[str, object]
    baseline_metrics: dict[str, object]
    training_row_count: int
    evaluation_row_count: int


@dataclass(frozen=True, slots=True)
class CandidateDatasetRow:
    """One feature-snapshot row joined to its after-the-fact label."""

    feature_snapshot_row_id: int | None
    forecast_issue_time_utc: datetime
    target_interval_start_utc: datetime
    target_interval_end_utc: datetime
    lead_hour: int
    feature_payload: dict[str, object]
    features: tuple[float, ...]
    actual_demand_mw: Decimal


def train_candidate_from_feature_snapshots(
    session: Session,
    *,
    config: CandidateTrainingConfig,
) -> CandidateTrainingResult:
    """Train, persist, evaluate, save, and gate a deterministic candidate model."""

    created_at = _coerce_aware_utc(config.created_at_utc) if config.created_at_utc else utc_now()
    training_run = _persist_training_run(
        session,
        config=config,
        status=ModelTrainingStatus.RUNNING,
        started_at_utc=created_at,
        created_at_utc=created_at,
    )
    session.flush()

    try:
        training_rows = load_candidate_rows(
            session,
            feature_version=config.feature_version,
            window_start_utc=config.training_window_start_utc,
            window_end_utc=config.training_window_end_utc,
        )
        evaluation_rows = load_candidate_rows(
            session,
            feature_version=config.feature_version,
            window_start_utc=config.evaluation_window_start_utc,
            window_end_utc=config.evaluation_window_end_utc,
        )
        if len(training_rows) < MINIMUM_TRAINING_ROWS:
            raise ValueError(f"insufficient training rows: {len(training_rows)}")
        if len(evaluation_rows) < MINIMUM_EVALUATION_ROWS:
            raise ValueError(f"insufficient evaluation rows: {len(evaluation_rows)}")

        model = make_gradient_boosting_candidate(random_state=config.random_state)
        model.fit(
            [list(row.features) for row in training_rows],
            [float(row.actual_demand_mw) for row in training_rows],
        )
        predictions = _predict_candidate(model, evaluation_rows, model_name=config.model_name)
        candidate_metrics = calculate_candidate_metrics(predictions)
        baseline_metrics = load_selected_baseline_metrics(
            session,
            selected_baseline_name=config.selected_baseline_name,
            evaluation_window_start_utc=config.evaluation_window_start_utc,
            evaluation_window_end_utc=config.evaluation_window_end_utc,
        )
        lineage = _lineage(config=config, training_row_count=len(training_rows))
        decision = evaluate_model_selection_gate(
            candidate_metrics=candidate_metrics,
            baseline_metrics=baseline_metrics,
            selected_baseline_name=config.selected_baseline_name,
            lineage_metadata=lineage,
        )
        saved_artifact = save_artifact(
            model,
            model_name=config.model_name,
            model_version=config.model_version,
            base_dir=config.artifact_dir,
        )
        artifact = persist_model_artifact_metadata(
            session,
            model_training_run_id=training_run.id,
            model_name=config.model_name,
            model_type=config.model_type,
            model_version=config.model_version,
            feature_version=config.feature_version,
            artifact_uri=saved_artifact.artifact_uri,
            artifact_hash=saved_artifact.artifact_hash,
            status=ModelArtifactStatus.AVAILABLE,
            training_window_start_utc=config.training_window_start_utc,
            training_window_end_utc=config.training_window_end_utc,
            evaluation_window_start_utc=config.evaluation_window_start_utc,
            evaluation_window_end_utc=config.evaluation_window_end_utc,
            parameters={
                "random_state": config.random_state,
                "feature_names": list(FEATURE_NAMES),
            },
            metrics_summary=candidate_metrics,
            lineage_metadata=lineage,
            created_at_utc=created_at,
        )
        selection_result = persist_model_selection_result(
            session,
            decision=decision,
            model_training_run_id=training_run.id,
            model_artifact_id=artifact.id,
            model_name=config.model_name,
            model_type=config.model_type,
            model_version=config.model_version,
            feature_version=config.feature_version,
            candidate_metrics=candidate_metrics,
            baseline_metrics=baseline_metrics,
            training_window_start_utc=config.training_window_start_utc,
            training_window_end_utc=config.training_window_end_utc,
            evaluation_window_start_utc=config.evaluation_window_start_utc,
            evaluation_window_end_utc=config.evaluation_window_end_utc,
            lineage_metadata=lineage,
            created_at_utc=created_at,
        )
        training_run.status = ModelTrainingStatus.SUCCEEDED.value
        training_run.completed_at_utc = created_at
        training_run.metrics_summary_json = candidate_metrics
        training_run.parameters_json = {
            "random_state": config.random_state,
            "split_strategy": config.split_strategy,
            "selected_baseline_name": config.selected_baseline_name,
        }
        training_run.lineage_metadata = {
            **lineage,
            "artifact_hash": saved_artifact.artifact_hash,
            "selection_status": selection_result.selection_status,
        }
        session.flush()

        return CandidateTrainingResult(
            training_run=training_run,
            artifact=artifact,
            selection_result=selection_result,
            candidate_metrics=candidate_metrics,
            baseline_metrics=baseline_metrics,
            training_row_count=len(training_rows),
            evaluation_row_count=len(evaluation_rows),
        )
    except Exception as exc:
        training_run.status = ModelTrainingStatus.FAILED.value
        training_run.completed_at_utc = created_at
        training_run.safe_error_detail = str(exc)[:1000]
        session.flush()
        return CandidateTrainingResult(
            training_run=training_run,
            artifact=None,
            selection_result=None,
            candidate_metrics={},
            baseline_metrics={},
            training_row_count=0,
            evaluation_row_count=0,
        )


def load_candidate_rows(
    session: Session,
    *,
    feature_version: str,
    window_start_utc: datetime,
    window_end_utc: datetime,
) -> list[CandidateDatasetRow]:
    """Load usable candidate rows from M04 feature snapshots and demand labels."""

    window_start = _coerce_aware_utc(window_start_utc)
    window_end = _coerce_aware_utc(window_end_utc)
    actuals_by_start = {
        row.interval_start_utc: row.demand_mw
        for row in session.scalars(
            select(IesoHourlyDemand).where(
                IesoHourlyDemand.is_current.is_(True),
                IesoHourlyDemand.interval_start_utc >= window_start,
                IesoHourlyDemand.interval_end_utc <= window_end,
            )
        )
    }
    snapshot_rows = session.scalars(
        select(FeatureSnapshotRow)
        .where(
            FeatureSnapshotRow.feature_version == feature_version,
            FeatureSnapshotRow.target_interval_start_utc >= window_start,
            FeatureSnapshotRow.target_interval_end_utc <= window_end,
        )
        .order_by(FeatureSnapshotRow.target_interval_start_utc, FeatureSnapshotRow.id)
    ).all()

    usable_rows = []
    for row in snapshot_rows:
        payload = parse_feature_payload(row.lineage_metadata)
        if not payload_uses_no_target_actuals(payload):
            continue
        features = feature_vector_from_payload(payload)
        actual = actuals_by_start.get(row.target_interval_start_utc)
        if features is None or actual is None:
            continue
        usable_rows.append(
            CandidateDatasetRow(
                feature_snapshot_row_id=row.id,
                forecast_issue_time_utc=row.forecast_issue_time_utc,
                target_interval_start_utc=row.target_interval_start_utc,
                target_interval_end_utc=row.target_interval_end_utc,
                lead_hour=row.lead_hour,
                feature_payload=payload,
                features=tuple(features),
                actual_demand_mw=actual,
            )
        )

    return usable_rows


def calculate_candidate_metrics(predictions: list[BaselinePrediction]) -> dict[str, object]:
    """Calculate candidate metrics using the M04 aggregate metric logic."""

    return {
        metric.metric_name: float(metric.metric_value)
        for metric in calculate_baseline_metrics(predictions)
    }


def load_selected_baseline_metrics(
    session: Session,
    *,
    selected_baseline_name: str,
    evaluation_window_start_utc: datetime,
    evaluation_window_end_utc: datetime,
) -> dict[str, object]:
    """Load persisted M04 aggregate metrics for a selected baseline."""

    query = (
        select(BaselineMetricResult)
        .join(
            BaselineForecastRun,
            BaselineMetricResult.baseline_forecast_run_id == BaselineForecastRun.id,
        )
        .where(BaselineForecastRun.baseline_name == selected_baseline_name)
        .order_by(BaselineMetricResult.created_at_utc.desc(), BaselineMetricResult.id.desc())
    )
    rows = list(session.scalars(query).all())
    metrics: dict[str, float] = {}
    for row in rows:
        if row.metric_name not in metrics:
            metrics[row.metric_name] = float(row.metric_value)

    if not metrics:
        raise ValueError(f"no persisted baseline metrics for {selected_baseline_name}")

    return {selected_baseline_name: metrics}


def _predict_candidate(
    model: CandidateRegressor,
    rows: list[CandidateDatasetRow],
    *,
    model_name: str,
) -> list[BaselinePrediction]:
    predictions = []
    for row in rows:
        raw_prediction = model.predict([list(row.features)])[0]
        predictions.append(
            BaselinePrediction(
                baseline_name=model_name,
                forecast_issue_time_utc=row.forecast_issue_time_utc,
                target_interval_start_utc=row.target_interval_start_utc,
                target_interval_end_utc=row.target_interval_end_utc,
                lead_hour=row.lead_hour,
                predicted_demand_mw=Decimal(str(raw_prediction)),
                actual_demand_mw=row.actual_demand_mw,
                prediction_status="predicted",
                feature_snapshot_row_id=row.feature_snapshot_row_id,
            )
        )

    return predictions


def _persist_training_run(
    session: Session,
    *,
    config: CandidateTrainingConfig,
    status: ModelTrainingStatus,
    started_at_utc: datetime,
    created_at_utc: datetime,
) -> ModelTrainingRun:
    run = ModelTrainingRun(
        model_name=config.model_name,
        model_type=config.model_type,
        model_version=config.model_version,
        feature_version=config.feature_version,
        status=status.value,
        training_window_start_utc=_coerce_aware_utc(config.training_window_start_utc),
        training_window_end_utc=_coerce_aware_utc(config.training_window_end_utc),
        evaluation_window_start_utc=_coerce_aware_utc(config.evaluation_window_start_utc),
        evaluation_window_end_utc=_coerce_aware_utc(config.evaluation_window_end_utc),
        parameters_json={"split_strategy": config.split_strategy},
        metrics_summary_json=None,
        lineage_metadata=None,
        started_at_utc=started_at_utc,
        completed_at_utc=None,
        created_at_utc=created_at_utc,
        safe_error_detail=None,
    )
    session.add(run)
    session.flush()

    return run


def _lineage(*, config: CandidateTrainingConfig, training_row_count: int) -> dict[str, object]:
    return {
        "model_name": config.model_name,
        "model_version": config.model_version,
        "model_type": config.model_type,
        "feature_version": config.feature_version,
        "training_window_start_utc": _coerce_aware_utc(
            config.training_window_start_utc
        ).isoformat(),
        "training_window_end_utc": _coerce_aware_utc(config.training_window_end_utc).isoformat(),
        "evaluation_window_start_utc": _coerce_aware_utc(
            config.evaluation_window_start_utc
        ).isoformat(),
        "evaluation_window_end_utc": _coerce_aware_utc(
            config.evaluation_window_end_utc
        ).isoformat(),
        "feature_source_table": "feature_snapshot_rows",
        "label_source_table": "ieso_hourly_demand",
        "training_row_count": training_row_count,
        "feature_names": list(FEATURE_NAMES),
    }


def _validate_window(start: datetime, end: datetime, field_name: str) -> None:
    start_utc = _coerce_aware_utc(start)
    end_utc = _coerce_aware_utc(end)
    if start_utc >= end_utc:
        raise ValueError(f"{field_name} start must be before end")


def _coerce_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("candidate training timestamps must be timezone-aware")

    return value.astimezone(UTC)


def utc_now() -> datetime:
    """Return the current aware UTC timestamp."""

    return datetime.now(UTC)
