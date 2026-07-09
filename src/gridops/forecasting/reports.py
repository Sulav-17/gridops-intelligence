"""Slice reports and persistence for M04 baseline evaluation."""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from gridops.forecasting.baselines import BaselinePrediction
from gridops.forecasting.metrics import MetricResult, calculate_baseline_metrics
from gridops.models import (
    BaselineForecastPrediction,
    BaselineForecastRun,
    BaselineMetricResult,
    BaselineSliceMetricResult,
)

DEFAULT_SLICE_DIMENSIONS = (
    "lead_hour",
    "target_hour",
    "day_of_week",
    "is_weekend",
    "month",
    "season",
)


@dataclass(frozen=True, slots=True)
class SliceMetricResult:
    """One metric result for one baseline evaluation slice."""

    baseline_name: str
    slice_name: str
    slice_value: str
    metric_name: str
    metric_value: Decimal
    row_count: int


@dataclass(frozen=True, slots=True)
class PersistedBaselineEvaluation:
    """Persisted baseline run, predictions, and metric rows."""

    run: BaselineForecastRun
    predictions: tuple[BaselineForecastPrediction, ...]
    metrics: tuple[BaselineMetricResult, ...]
    slice_metrics: tuple[BaselineSliceMetricResult, ...]


def calculate_slice_metrics(
    predictions: Sequence[BaselinePrediction],
    *,
    dimensions: Sequence[str] = DEFAULT_SLICE_DIMENSIONS,
) -> list[SliceMetricResult]:
    """Calculate metric results by deterministic slice dimensions."""

    results: list[SliceMetricResult] = []
    for dimension in dimensions:
        grouped: dict[str, list[BaselinePrediction]] = {}
        for prediction in predictions:
            grouped.setdefault(_slice_value(prediction, dimension), []).append(prediction)
        for value, group in sorted(grouped.items()):
            for metric in calculate_baseline_metrics(group):
                results.append(
                    SliceMetricResult(
                        baseline_name=metric.baseline_name,
                        slice_name=dimension,
                        slice_value=value,
                        metric_name=metric.metric_name,
                        metric_value=metric.metric_value,
                        row_count=metric.prediction_count,
                    )
                )

    return results


def persist_baseline_evaluation(
    session: Session,
    *,
    baseline_name: str,
    feature_version: str,
    predictions: Sequence[BaselinePrediction],
    metrics: Sequence[MetricResult],
    slice_metrics: Sequence[SliceMetricResult],
    started_at_utc: datetime,
    completed_at_utc: datetime,
    training_window_start_utc: datetime | None = None,
    training_window_end_utc: datetime | None = None,
    evaluation_window_start_utc: datetime | None = None,
    evaluation_window_end_utc: datetime | None = None,
    run_metadata: dict[str, object] | None = None,
) -> PersistedBaselineEvaluation:
    """Persist baseline run, prediction rows, aggregate metrics, and slice metrics."""

    run = BaselineForecastRun(
        baseline_name=baseline_name,
        feature_version=feature_version,
        status="succeeded",
        training_window_start_utc=training_window_start_utc,
        training_window_end_utc=training_window_end_utc,
        evaluation_window_start_utc=evaluation_window_start_utc,
        evaluation_window_end_utc=evaluation_window_end_utc,
        quality_blocking_behavior="block_on_m03_error_or_critical",
        run_metadata=json.dumps(run_metadata or {}, sort_keys=True),
        started_at_utc=started_at_utc,
        completed_at_utc=completed_at_utc,
        safe_error_detail=None,
    )
    session.add(run)
    session.flush()

    prediction_rows = tuple(
        _persist_prediction(
            session, run_id=run.id, prediction=prediction, created_at=completed_at_utc
        )
        for prediction in predictions
    )
    metric_rows = tuple(
        _persist_metric(session, run_id=run.id, metric=metric, created_at=completed_at_utc)
        for metric in metrics
    )
    slice_metric_rows = tuple(
        _persist_slice_metric(
            session,
            run_id=run.id,
            metric=metric,
            created_at=completed_at_utc,
        )
        for metric in slice_metrics
    )
    session.flush()

    return PersistedBaselineEvaluation(
        run=run,
        predictions=prediction_rows,
        metrics=metric_rows,
        slice_metrics=slice_metric_rows,
    )


def _persist_prediction(
    session: Session,
    *,
    run_id: int,
    prediction: BaselinePrediction,
    created_at: datetime,
) -> BaselineForecastPrediction:
    row = BaselineForecastPrediction(
        baseline_forecast_run_id=run_id,
        feature_snapshot_row_id=prediction.feature_snapshot_row_id,
        forecast_issue_time_utc=prediction.forecast_issue_time_utc,
        target_interval_start_utc=prediction.target_interval_start_utc,
        target_interval_end_utc=prediction.target_interval_end_utc,
        lead_hour=prediction.lead_hour,
        predicted_demand_mw=prediction.predicted_demand_mw,
        actual_demand_mw=prediction.actual_demand_mw,
        prediction_status=prediction.prediction_status,
        lineage_metadata=prediction.lineage_metadata,
        created_at_utc=created_at,
    )
    session.add(row)

    return row


def _persist_metric(
    session: Session,
    *,
    run_id: int,
    metric: MetricResult,
    created_at: datetime,
) -> BaselineMetricResult:
    row = BaselineMetricResult(
        baseline_forecast_run_id=run_id,
        metric_name=metric.metric_name,
        metric_value=metric.metric_value,
        metric_unit="mw",
        evaluation_window_start_utc=None,
        evaluation_window_end_utc=None,
        created_at_utc=created_at,
        lineage_metadata=json.dumps({"prediction_count": metric.prediction_count}, sort_keys=True),
    )
    session.add(row)

    return row


def _persist_slice_metric(
    session: Session,
    *,
    run_id: int,
    metric: SliceMetricResult,
    created_at: datetime,
) -> BaselineSliceMetricResult:
    row = BaselineSliceMetricResult(
        baseline_forecast_run_id=run_id,
        slice_name=metric.slice_name,
        slice_value=metric.slice_value,
        metric_name=metric.metric_name,
        metric_value=metric.metric_value,
        metric_unit="mw",
        row_count=metric.row_count,
        created_at_utc=created_at,
        lineage_metadata=None,
    )
    session.add(row)

    return row


def _slice_value(prediction: BaselinePrediction, dimension: str) -> str:
    target = prediction.target_interval_start_utc
    if dimension == "lead_hour":
        return str(prediction.lead_hour)
    if dimension == "target_hour":
        return str(target.hour)
    if dimension == "day_of_week":
        return str(target.weekday())
    if dimension == "is_weekend":
        return str(target.weekday() >= 5).lower()
    if dimension == "month":
        return str(target.month)
    if dimension == "season":
        return _season_for_month(target.month)

    raise ValueError(f"unsupported slice dimension: {dimension}")


def _season_for_month(month: int) -> str:
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "fall"
