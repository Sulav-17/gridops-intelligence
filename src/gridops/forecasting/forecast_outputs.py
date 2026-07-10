"""Production forecast output generation foundation for M05."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from gridops.forecasting.artifacts import load_artifact
from gridops.forecasting.candidate_models import CandidateRegressor, feature_vector_from_payload
from gridops.forecasting.feature_snapshots import persist_feature_snapshot
from gridops.forecasting.issue_contract import (
    DEFAULT_FORECAST_TYPE,
    ForecastIssueContract,
    require_aware_utc_datetime,
)
from gridops.forecasting.model_contracts import ForecastRunStatus, ModelArtifactStatus
from gridops.models import (
    FeatureSnapshotRow,
    FeatureSnapshotRun,
    ForecastPeakOutput,
    ForecastRampOutput,
    ModelArtifact,
    ModelSelectionResult,
    ProductionForecastPrediction,
    ProductionForecastRun,
)

PREDICTION_TYPE_P50_ONLY = "p50_only"


@dataclass(frozen=True, slots=True)
class ForecastGenerationConfig:
    """Configuration for one production forecast generation attempt."""

    model_artifact_id: int
    forecast_issue_time_utc: datetime
    horizon_hours: int = 24
    forecast_type: str = DEFAULT_FORECAST_TYPE
    created_at_utc: datetime | None = None
    build_missing_feature_snapshot: bool = True

    def __post_init__(self) -> None:
        require_aware_utc_datetime(self.forecast_issue_time_utc)
        if self.horizon_hours <= 0:
            raise ValueError("horizon_hours must be positive")
        if not self.forecast_type:
            raise ValueError("forecast_type must be non-empty")


@dataclass(frozen=True, slots=True)
class ForecastGenerationResult:
    """Persisted output from a production forecast generation attempt."""

    forecast_run: ProductionForecastRun
    predictions: tuple[ProductionForecastPrediction, ...]
    peak_output: ForecastPeakOutput | None
    ramp_outputs: tuple[ForecastRampOutput, ...]


def generate_forecast_from_selected_artifact(
    session: Session,
    *,
    config: ForecastGenerationConfig,
) -> ForecastGenerationResult:
    """Generate and persist forecast outputs from a selected model artifact."""

    created_at = _coerce_aware_utc(config.created_at_utc) if config.created_at_utc else utc_now()
    issue_time = require_aware_utc_datetime(config.forecast_issue_time_utc)
    artifact = session.get(ModelArtifact, config.model_artifact_id)
    if artifact is None:
        raise ValueError(f"model artifact {config.model_artifact_id} does not exist")

    forecast_run = _persist_forecast_run(
        session,
        artifact=artifact,
        feature_snapshot_run_id=None,
        forecast_issue_time_utc=issue_time,
        status=ForecastRunStatus.RUNNING,
        created_at_utc=created_at,
    )
    session.flush()

    try:
        _validate_artifact_is_selected_and_usable(session, artifact)
        snapshot_run = _get_or_build_feature_snapshot_run(
            session,
            artifact=artifact,
            config=config,
            created_at_utc=created_at,
        )
        forecast_run.feature_snapshot_run_id = snapshot_run.id
        if snapshot_run.status == "blocked":
            raise ValueError("feature snapshot is blocked")
        if snapshot_run.status != "succeeded":
            raise ValueError(f"feature snapshot is not usable: {snapshot_run.status}")

        rows = _load_snapshot_rows(session, snapshot_run)
        if not rows:
            raise ValueError("feature snapshot has no rows")

        model = load_artifact(artifact.artifact_uri)
        predictions = _persist_predictions(
            session,
            model=model,
            rows=rows,
            forecast_run=forecast_run,
            artifact=artifact,
            created_at_utc=created_at,
        )
        peak = _persist_peak_output(
            session,
            forecast_run=forecast_run,
            predictions=predictions,
            created_at_utc=created_at,
        )
        ramps = _persist_ramp_outputs(
            session,
            forecast_run=forecast_run,
            predictions=predictions,
            created_at_utc=created_at,
        )

        forecast_run.status = ForecastRunStatus.SUCCEEDED.value
        forecast_run.completed_at_utc = created_at
        forecast_run.lineage_metadata = _run_lineage(
            artifact=artifact,
            feature_snapshot_run_id=snapshot_run.id,
            forecast_issue_time_utc=issue_time,
        )
        session.flush()

        return ForecastGenerationResult(
            forecast_run=forecast_run,
            predictions=tuple(predictions),
            peak_output=peak,
            ramp_outputs=tuple(ramps),
        )
    except Exception as exc:
        forecast_run.status = ForecastRunStatus.BLOCKED.value
        forecast_run.completed_at_utc = created_at
        forecast_run.safe_error_detail = str(exc)[:1000]
        session.flush()
        return ForecastGenerationResult(
            forecast_run=forecast_run,
            predictions=(),
            peak_output=None,
            ramp_outputs=(),
        )


def _validate_artifact_is_selected_and_usable(session: Session, artifact: ModelArtifact) -> None:
    if artifact.status != ModelArtifactStatus.AVAILABLE.value:
        raise ValueError(f"model artifact is not available: {artifact.status}")

    selected = session.scalar(
        select(ModelSelectionResult).where(
            ModelSelectionResult.model_artifact_id == artifact.id,
            ModelSelectionResult.selection_status == "selected",
        )
    )
    if selected is None:
        raise ValueError("model artifact is not selected")


def _get_or_build_feature_snapshot_run(
    session: Session,
    *,
    artifact: ModelArtifact,
    config: ForecastGenerationConfig,
    created_at_utc: datetime,
) -> FeatureSnapshotRun:
    issue_time = require_aware_utc_datetime(config.forecast_issue_time_utc)
    existing = session.scalar(
        select(FeatureSnapshotRun)
        .join(
            FeatureSnapshotRow, FeatureSnapshotRow.feature_snapshot_run_id == FeatureSnapshotRun.id
        )
        .where(
            FeatureSnapshotRun.feature_version == artifact.feature_version,
            FeatureSnapshotRow.forecast_issue_time_utc == issue_time,
        )
        .order_by(FeatureSnapshotRun.id.desc())
    )
    if existing is not None:
        return existing

    blocked = session.scalar(
        select(FeatureSnapshotRun)
        .where(
            FeatureSnapshotRun.feature_version == artifact.feature_version,
            FeatureSnapshotRun.status == "blocked",
        )
        .order_by(FeatureSnapshotRun.id.desc())
    )
    if blocked is not None:
        return blocked

    if not config.build_missing_feature_snapshot:
        raise ValueError("feature snapshot is missing")

    contract = ForecastIssueContract(
        forecast_issue_time_utc=issue_time,
        horizon_length_hours=config.horizon_hours,
        forecast_type=config.forecast_type,
        feature_version=artifact.feature_version,
    )
    return persist_feature_snapshot(
        session,
        contract=contract,
        generated_at_utc=created_at_utc,
    ).snapshot_run


def _load_snapshot_rows(
    session: Session, snapshot_run: FeatureSnapshotRun
) -> list[FeatureSnapshotRow]:
    return list(
        session.scalars(
            select(FeatureSnapshotRow)
            .where(FeatureSnapshotRow.feature_snapshot_run_id == snapshot_run.id)
            .order_by(FeatureSnapshotRow.lead_hour, FeatureSnapshotRow.target_interval_start_utc)
        ).all()
    )


def _persist_predictions(
    session: Session,
    *,
    model: CandidateRegressor,
    rows: list[FeatureSnapshotRow],
    forecast_run: ProductionForecastRun,
    artifact: ModelArtifact,
    created_at_utc: datetime,
) -> list[ProductionForecastPrediction]:
    predicted_rows: list[tuple[FeatureSnapshotRow, Decimal]] = []
    for row in rows:
        payload = _payload(row)
        features = feature_vector_from_payload(payload)
        if features is None:
            raise ValueError(f"feature snapshot row {row.id} is missing required model inputs")
        raw_prediction = model.predict([features])[0]
        predicted_rows.append((row, Decimal(str(raw_prediction))))

    predictions = []
    for row, p50 in predicted_rows:
        prediction = ProductionForecastPrediction(
            production_forecast_run_id=forecast_run.id,
            feature_snapshot_row_id=row.id,
            forecast_issue_time_utc=row.forecast_issue_time_utc,
            target_interval_start_utc=row.target_interval_start_utc,
            target_interval_end_utc=row.target_interval_end_utc,
            lead_hour=row.lead_hour,
            p10_demand_mw=None,
            p50_demand_mw=p50,
            p90_demand_mw=None,
            point_forecast_demand_mw=None,
            prediction_type=PREDICTION_TYPE_P50_ONLY,
            lineage_metadata={
                "model_artifact_id": artifact.id,
                "model_training_run_id": artifact.model_training_run_id,
                "feature_snapshot_run_id": row.feature_snapshot_run_id,
                "feature_snapshot_row_id": row.id,
                "feature_version": artifact.feature_version,
            },
            created_at_utc=created_at_utc,
        )
        session.add(prediction)
        predictions.append(prediction)
    session.flush()

    return predictions


def _persist_peak_output(
    session: Session,
    *,
    forecast_run: ProductionForecastRun,
    predictions: list[ProductionForecastPrediction],
    created_at_utc: datetime,
) -> ForecastPeakOutput:
    peak_prediction = max(
        predictions,
        key=lambda prediction: prediction.p50_demand_mw or Decimal("0"),
    )
    peak = ForecastPeakOutput(
        production_forecast_run_id=forecast_run.id,
        peak_target_interval_start_utc=peak_prediction.target_interval_start_utc,
        peak_target_interval_end_utc=peak_prediction.target_interval_end_utc,
        peak_demand_mw=peak_prediction.p50_demand_mw or Decimal("0"),
        peak_lead_hour=peak_prediction.lead_hour,
        lineage_metadata={"source": "production_forecast_predictions"},
        created_at_utc=created_at_utc,
    )
    session.add(peak)
    session.flush()

    return peak


def _persist_ramp_outputs(
    session: Session,
    *,
    forecast_run: ProductionForecastRun,
    predictions: list[ProductionForecastPrediction],
    created_at_utc: datetime,
) -> list[ForecastRampOutput]:
    ramps = []
    ordered = sorted(predictions, key=lambda prediction: prediction.target_interval_start_utc)
    for previous, current in zip(ordered, ordered[1:], strict=False):
        previous_value = previous.p50_demand_mw or Decimal("0")
        current_value = current.p50_demand_mw or Decimal("0")
        ramp_mw = current_value - previous_value
        ramp = ForecastRampOutput(
            production_forecast_run_id=forecast_run.id,
            target_interval_start_utc=current.target_interval_start_utc,
            previous_target_interval_start_utc=previous.target_interval_start_utc,
            forecast_ramp_mw=ramp_mw,
            absolute_ramp_mw=abs(ramp_mw),
            lineage_metadata={
                "current_prediction_id": current.id,
                "previous_prediction_id": previous.id,
            },
            created_at_utc=created_at_utc,
        )
        session.add(ramp)
        ramps.append(ramp)
    session.flush()

    return ramps


def _persist_forecast_run(
    session: Session,
    *,
    artifact: ModelArtifact,
    feature_snapshot_run_id: int | None,
    forecast_issue_time_utc: datetime,
    status: ForecastRunStatus,
    created_at_utc: datetime,
) -> ProductionForecastRun:
    run = ProductionForecastRun(
        model_artifact_id=artifact.id,
        feature_snapshot_run_id=feature_snapshot_run_id,
        model_name=artifact.model_name,
        model_type=artifact.model_type,
        model_version=artifact.model_version,
        feature_version=artifact.feature_version,
        forecast_issue_time_utc=forecast_issue_time_utc,
        status=status.value,
        quality_status=None,
        lineage_metadata=None,
        started_at_utc=created_at_utc,
        completed_at_utc=None,
        created_at_utc=created_at_utc,
        safe_error_detail=None,
    )
    session.add(run)

    return run


def _payload(row: FeatureSnapshotRow) -> dict[str, object]:
    parsed = json.loads(row.lineage_metadata or "{}")
    if not isinstance(parsed, dict):
        return {}

    return parsed


def _run_lineage(
    *,
    artifact: ModelArtifact,
    feature_snapshot_run_id: int,
    forecast_issue_time_utc: datetime,
) -> dict[str, object]:
    return {
        "model_artifact_id": artifact.id,
        "model_training_run_id": artifact.model_training_run_id,
        "feature_snapshot_run_id": feature_snapshot_run_id,
        "feature_version": artifact.feature_version,
        "forecast_issue_time_utc": forecast_issue_time_utc.isoformat(),
    }


def _coerce_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("forecast generation timestamps must be timezone-aware")

    return value.astimezone(UTC)


def utc_now() -> datetime:
    """Return the current aware UTC timestamp."""

    return datetime.now(UTC)
