"""Minimal M05 model performance and drift monitoring foundations."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from gridops.forecasting.baselines import BaselinePrediction
from gridops.forecasting.candidate_models import FEATURE_NAMES, feature_vector_from_payload
from gridops.forecasting.metrics import calculate_baseline_metrics
from gridops.models import (
    FeatureSnapshotRow,
    IesoHourlyDemand,
    ModelArtifact,
    ModelDriftSummary,
    ModelPerformanceSummary,
    ProductionForecastPrediction,
    ProductionForecastRun,
)

DRIFT_METRIC_NAME = "absolute_mean_difference"
NO_DATA_FEATURE_NAME = "__no_data__"


@dataclass(frozen=True, slots=True)
class PerformanceMonitoringConfig:
    """Configuration for one forecast-vs-actual performance summary run."""

    model_artifact_id: int
    evaluation_window_start_utc: datetime
    evaluation_window_end_utc: datetime
    created_at_utc: datetime | None = None

    def __post_init__(self) -> None:
        _validate_window(
            self.evaluation_window_start_utc,
            self.evaluation_window_end_utc,
            "evaluation window",
        )


@dataclass(frozen=True, slots=True)
class DriftMonitoringConfig:
    """Configuration for one deterministic feature-drift summary run."""

    model_artifact_id: int
    baseline_window_start_utc: datetime
    baseline_window_end_utc: datetime
    comparison_window_start_utc: datetime
    comparison_window_end_utc: datetime
    feature_version: str | None = None
    created_at_utc: datetime | None = None

    def __post_init__(self) -> None:
        _validate_window(
            self.baseline_window_start_utc,
            self.baseline_window_end_utc,
            "baseline window",
        )
        _validate_window(
            self.comparison_window_start_utc,
            self.comparison_window_end_utc,
            "comparison window",
        )


def summarize_model_performance(
    session: Session,
    *,
    config: PerformanceMonitoringConfig,
) -> list[ModelPerformanceSummary]:
    """Persist MAE, RMSE, WAPE, and bias for forecasts with available actuals."""

    created_at = _coerce_aware_utc(config.created_at_utc) if config.created_at_utc else utc_now()
    artifact = _require_artifact(session, config.model_artifact_id)
    predictions = _performance_predictions(session, config=config, artifact=artifact)
    metrics = calculate_baseline_metrics(predictions)
    row_count = metrics[0].prediction_count if metrics else 0
    summaries = []
    for metric in metrics:
        summary = ModelPerformanceSummary(
            model_artifact_id=artifact.id,
            model_name=artifact.model_name,
            model_type=artifact.model_type,
            model_version=artifact.model_version,
            feature_version=artifact.feature_version,
            metric_name=metric.metric_name,
            metric_value=metric.metric_value,
            metric_unit="MW" if metric.metric_name in {"mae", "rmse", "bias"} else None,
            row_count=row_count,
            evaluation_window_start_utc=_coerce_aware_utc(config.evaluation_window_start_utc),
            evaluation_window_end_utc=_coerce_aware_utc(config.evaluation_window_end_utc),
            lineage_metadata={
                "source": "production_forecast_predictions",
                "actual_source": "ieso_hourly_demand",
                "model_artifact_id": artifact.id,
                "prediction_count": row_count,
            },
            created_at_utc=created_at,
        )
        session.add(summary)
        summaries.append(summary)
    session.flush()

    return summaries


def summarize_feature_drift(
    session: Session,
    *,
    config: DriftMonitoringConfig,
) -> list[ModelDriftSummary]:
    """Persist simple feature mean-difference summaries for two time windows."""

    created_at = _coerce_aware_utc(config.created_at_utc) if config.created_at_utc else utc_now()
    artifact = _require_artifact(session, config.model_artifact_id)
    feature_version = config.feature_version or artifact.feature_version
    baseline_vectors = _feature_vectors(
        session,
        feature_version=feature_version,
        window_start_utc=config.baseline_window_start_utc,
        window_end_utc=config.baseline_window_end_utc,
    )
    comparison_vectors = _feature_vectors(
        session,
        feature_version=feature_version,
        window_start_utc=config.comparison_window_start_utc,
        window_end_utc=config.comparison_window_end_utc,
    )

    if not baseline_vectors or not comparison_vectors:
        summary = _drift_summary(
            artifact=artifact,
            config=config,
            feature_name=NO_DATA_FEATURE_NAME,
            drift_score=None,
            summary_json={
                "status": "no_data",
                "baseline_row_count": len(baseline_vectors),
                "comparison_row_count": len(comparison_vectors),
            },
            created_at_utc=created_at,
        )
        session.add(summary)
        session.flush()
        return [summary]

    summaries = []
    baseline_means = _column_means(baseline_vectors)
    comparison_means = _column_means(comparison_vectors)
    for feature_name, baseline_mean, comparison_mean in zip(
        FEATURE_NAMES,
        baseline_means,
        comparison_means,
        strict=True,
    ):
        score = abs(comparison_mean - baseline_mean)
        summary = _drift_summary(
            artifact=artifact,
            config=config,
            feature_name=feature_name,
            drift_score=score,
            summary_json={
                "status": "calculated",
                "baseline_mean": str(baseline_mean),
                "comparison_mean": str(comparison_mean),
                "baseline_row_count": len(baseline_vectors),
                "comparison_row_count": len(comparison_vectors),
            },
            created_at_utc=created_at,
        )
        session.add(summary)
        summaries.append(summary)
    session.flush()

    return summaries


def _performance_predictions(
    session: Session,
    *,
    config: PerformanceMonitoringConfig,
    artifact: ModelArtifact,
) -> list[BaselinePrediction]:
    actuals_by_start = {
        row.interval_start_utc: row.demand_mw
        for row in session.scalars(
            select(IesoHourlyDemand).where(
                IesoHourlyDemand.is_current.is_(True),
                IesoHourlyDemand.interval_start_utc
                >= _coerce_aware_utc(config.evaluation_window_start_utc),
                IesoHourlyDemand.interval_end_utc
                <= _coerce_aware_utc(config.evaluation_window_end_utc),
            )
        )
    }
    rows = session.scalars(
        select(ProductionForecastPrediction)
        .join(
            ProductionForecastRun,
            ProductionForecastPrediction.production_forecast_run_id == ProductionForecastRun.id,
        )
        .where(
            ProductionForecastRun.model_artifact_id == artifact.id,
            ProductionForecastRun.status == "succeeded",
            ProductionForecastPrediction.target_interval_start_utc
            >= _coerce_aware_utc(config.evaluation_window_start_utc),
            ProductionForecastPrediction.target_interval_end_utc
            <= _coerce_aware_utc(config.evaluation_window_end_utc),
        )
        .order_by(ProductionForecastPrediction.target_interval_start_utc)
    ).all()

    predictions = []
    for row in rows:
        predicted = row.p50_demand_mw or row.point_forecast_demand_mw
        actual = actuals_by_start.get(row.target_interval_start_utc)
        if predicted is None or actual is None:
            continue
        predictions.append(
            BaselinePrediction(
                baseline_name=artifact.model_name,
                forecast_issue_time_utc=row.forecast_issue_time_utc,
                target_interval_start_utc=row.target_interval_start_utc,
                target_interval_end_utc=row.target_interval_end_utc,
                lead_hour=row.lead_hour,
                predicted_demand_mw=predicted,
                actual_demand_mw=actual,
                prediction_status="predicted",
                feature_snapshot_row_id=row.feature_snapshot_row_id,
            )
        )

    return predictions


def _feature_vectors(
    session: Session,
    *,
    feature_version: str,
    window_start_utc: datetime,
    window_end_utc: datetime,
) -> list[list[float]]:
    rows = session.scalars(
        select(FeatureSnapshotRow)
        .where(
            FeatureSnapshotRow.feature_version == feature_version,
            FeatureSnapshotRow.target_interval_start_utc >= _coerce_aware_utc(window_start_utc),
            FeatureSnapshotRow.target_interval_end_utc <= _coerce_aware_utc(window_end_utc),
        )
        .order_by(FeatureSnapshotRow.target_interval_start_utc, FeatureSnapshotRow.id)
    ).all()
    vectors = []
    for row in rows:
        payload = _payload(row)
        vector = feature_vector_from_payload(payload)
        if vector is not None:
            vectors.append(vector)

    return vectors


def _drift_summary(
    *,
    artifact: ModelArtifact,
    config: DriftMonitoringConfig,
    feature_name: str,
    drift_score: Decimal | None,
    summary_json: dict[str, object],
    created_at_utc: datetime,
) -> ModelDriftSummary:
    return ModelDriftSummary(
        model_artifact_id=artifact.id,
        model_name=artifact.model_name,
        model_type=artifact.model_type,
        model_version=artifact.model_version,
        feature_version=config.feature_version or artifact.feature_version,
        feature_name=feature_name,
        drift_metric_name=DRIFT_METRIC_NAME,
        drift_score=drift_score,
        baseline_window_start_utc=_coerce_aware_utc(config.baseline_window_start_utc),
        baseline_window_end_utc=_coerce_aware_utc(config.baseline_window_end_utc),
        comparison_window_start_utc=_coerce_aware_utc(config.comparison_window_start_utc),
        comparison_window_end_utc=_coerce_aware_utc(config.comparison_window_end_utc),
        summary_json=summary_json,
        lineage_metadata={
            "source": "feature_snapshot_rows",
            "model_artifact_id": artifact.id,
            "feature_version": config.feature_version or artifact.feature_version,
        },
        created_at_utc=created_at_utc,
    )


def _column_means(vectors: list[list[float]]) -> list[Decimal]:
    return [
        sum(Decimal(str(vector[index])) for vector in vectors) / Decimal(len(vectors))
        for index in range(len(FEATURE_NAMES))
    ]


def _payload(row: FeatureSnapshotRow) -> dict[str, object]:
    parsed = json.loads(row.lineage_metadata or "{}")
    if not isinstance(parsed, dict):
        return {}

    return parsed


def _require_artifact(session: Session, model_artifact_id: int) -> ModelArtifact:
    artifact = session.get(ModelArtifact, model_artifact_id)
    if artifact is None:
        raise ValueError(f"model artifact {model_artifact_id} does not exist")

    return artifact


def _validate_window(start: datetime, end: datetime, field_name: str) -> None:
    start_utc = _coerce_aware_utc(start)
    end_utc = _coerce_aware_utc(end)
    if start_utc >= end_utc:
        raise ValueError(f"{field_name} start must be before end")


def _coerce_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("monitoring timestamps must be timezone-aware")

    return value.astimezone(UTC)


def utc_now() -> datetime:
    """Return the current aware UTC timestamp."""

    return datetime.now(UTC)
