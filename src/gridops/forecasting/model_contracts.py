"""Typed M05 production forecasting and MLOps contracts."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from gridops.forecasting.issue_contract import require_aware_utc_datetime


class ModelTrainingStatus(StrEnum):
    """Lifecycle status for a persisted candidate training run."""

    PLANNED = "planned"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"


class ModelArtifactStatus(StrEnum):
    """Lifecycle status for a persisted model artifact record."""

    PENDING = "pending"
    AVAILABLE = "available"
    FAILED = "failed"
    DEPRECATED = "deprecated"


class ModelSelectionStatus(StrEnum):
    """Decision status for an explicit model-selection gate."""

    EVALUATED = "evaluated"
    SELECTED = "selected"
    REJECTED = "rejected"
    FAILED = "failed"


class ForecastRunStatus(StrEnum):
    """Lifecycle status for a production forecast run."""

    PLANNED = "planned"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class ModelTrainingRunContract:
    """Metadata contract for a candidate training run."""

    model_name: str
    model_type: str
    model_version: str
    feature_version: str
    status: ModelTrainingStatus
    training_window_start_utc: datetime
    training_window_end_utc: datetime
    evaluation_window_start_utc: datetime
    evaluation_window_end_utc: datetime
    parameters: dict[str, object] = field(default_factory=dict)
    metrics_summary: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty(self.model_name, "model_name")
        _require_non_empty(self.model_type, "model_type")
        _require_non_empty(self.model_version, "model_version")
        _require_non_empty(self.feature_version, "feature_version")
        _validate_time_window(
            self.training_window_start_utc,
            self.training_window_end_utc,
            "training window",
        )
        _validate_time_window(
            self.evaluation_window_start_utc,
            self.evaluation_window_end_utc,
            "evaluation window",
        )


@dataclass(frozen=True, slots=True)
class ModelArtifactContract:
    """Metadata contract for a persisted model artifact pointer."""

    model_name: str
    model_type: str
    model_version: str
    feature_version: str
    artifact_uri: str
    artifact_hash: str
    status: ModelArtifactStatus

    def __post_init__(self) -> None:
        _require_non_empty(self.model_name, "model_name")
        _require_non_empty(self.model_type, "model_type")
        _require_non_empty(self.model_version, "model_version")
        _require_non_empty(self.feature_version, "feature_version")
        _require_non_empty(self.artifact_uri, "artifact_uri")
        _require_non_empty(self.artifact_hash, "artifact_hash")


@dataclass(frozen=True, slots=True)
class ModelSelectionContract:
    """Contract for one model-selection gate result."""

    model_name: str
    model_type: str
    model_version: str
    feature_version: str
    selection_status: ModelSelectionStatus
    selection_reason: str
    candidate_metrics: dict[str, object]
    baseline_metrics: dict[str, object]
    training_window_start_utc: datetime
    training_window_end_utc: datetime
    evaluation_window_start_utc: datetime
    evaluation_window_end_utc: datetime

    def __post_init__(self) -> None:
        _require_non_empty(self.selection_reason, "selection_reason")
        _require_json_object(self.candidate_metrics, "candidate_metrics")
        _require_json_object(self.baseline_metrics, "baseline_metrics")
        _validate_time_window(
            self.training_window_start_utc,
            self.training_window_end_utc,
            "training window",
        )
        _validate_time_window(
            self.evaluation_window_start_utc,
            self.evaluation_window_end_utc,
            "evaluation window",
        )


@dataclass(frozen=True, slots=True)
class ForecastPredictionContract:
    """Contract for one production forecast prediction row."""

    forecast_issue_time_utc: datetime
    target_interval_start_utc: datetime
    target_interval_end_utc: datetime
    lead_hour: int
    prediction_type: str
    p50_demand_mw: Decimal | None = None
    point_forecast_demand_mw: Decimal | None = None
    p10_demand_mw: Decimal | None = None
    p90_demand_mw: Decimal | None = None

    def __post_init__(self) -> None:
        require_aware_utc_datetime(self.forecast_issue_time_utc)
        _validate_time_window(
            self.target_interval_start_utc,
            self.target_interval_end_utc,
            "target interval",
        )
        if self.lead_hour <= 0:
            raise ValueError("lead_hour must be positive")
        _require_non_empty(self.prediction_type, "prediction_type")
        if self.p50_demand_mw is None and self.point_forecast_demand_mw is None:
            raise ValueError("p50_demand_mw or point_forecast_demand_mw is required")
        for field_name, value in (
            ("p10_demand_mw", self.p10_demand_mw),
            ("p50_demand_mw", self.p50_demand_mw),
            ("p90_demand_mw", self.p90_demand_mw),
            ("point_forecast_demand_mw", self.point_forecast_demand_mw),
        ):
            _validate_optional_nonnegative_decimal(value, field_name)
        if (
            self.p10_demand_mw is not None
            and self.p50_demand_mw is not None
            and self.p10_demand_mw > self.p50_demand_mw
        ):
            raise ValueError("p10_demand_mw cannot exceed p50_demand_mw")
        if (
            self.p90_demand_mw is not None
            and self.p50_demand_mw is not None
            and self.p90_demand_mw < self.p50_demand_mw
        ):
            raise ValueError("p90_demand_mw cannot be below p50_demand_mw")


@dataclass(frozen=True, slots=True)
class PeakOutputContract:
    """Contract for peak-demand summary output."""

    peak_target_interval_start_utc: datetime
    peak_target_interval_end_utc: datetime
    peak_demand_mw: Decimal
    peak_lead_hour: int

    def __post_init__(self) -> None:
        _validate_time_window(
            self.peak_target_interval_start_utc,
            self.peak_target_interval_end_utc,
            "peak target interval",
        )
        if self.peak_lead_hour <= 0:
            raise ValueError("peak_lead_hour must be positive")
        _validate_nonnegative_decimal(self.peak_demand_mw, "peak_demand_mw")


@dataclass(frozen=True, slots=True)
class RampOutputContract:
    """Contract for target-to-previous-target ramp output."""

    target_interval_start_utc: datetime
    previous_target_interval_start_utc: datetime
    forecast_ramp_mw: Decimal
    absolute_ramp_mw: Decimal

    def __post_init__(self) -> None:
        target = require_aware_utc_datetime(self.target_interval_start_utc)
        previous = require_aware_utc_datetime(self.previous_target_interval_start_utc)
        if previous >= target:
            raise ValueError("previous_target_interval_start_utc must be before target")
        _validate_nonnegative_decimal(self.absolute_ramp_mw, "absolute_ramp_mw")
        if abs(self.forecast_ramp_mw) != self.absolute_ramp_mw:
            raise ValueError("absolute_ramp_mw must equal abs(forecast_ramp_mw)")


@dataclass(frozen=True, slots=True)
class PerformanceSummaryContract:
    """Contract for deterministic model-performance metric summaries."""

    model_name: str
    model_type: str
    model_version: str
    feature_version: str
    metric_name: str
    metric_value: Decimal
    row_count: int
    evaluation_window_start_utc: datetime
    evaluation_window_end_utc: datetime
    metric_unit: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.metric_name, "metric_name")
        if self.row_count < 0:
            raise ValueError("row_count cannot be negative")
        _validate_time_window(
            self.evaluation_window_start_utc,
            self.evaluation_window_end_utc,
            "evaluation window",
        )


@dataclass(frozen=True, slots=True)
class DriftSummaryContract:
    """Contract for deterministic drift summaries."""

    model_name: str
    model_type: str
    model_version: str
    feature_version: str
    feature_name: str
    drift_metric_name: str
    baseline_window_start_utc: datetime
    baseline_window_end_utc: datetime
    comparison_window_start_utc: datetime
    comparison_window_end_utc: datetime
    drift_score: Decimal | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.feature_name, "feature_name")
        _require_non_empty(self.drift_metric_name, "drift_metric_name")
        _validate_time_window(
            self.baseline_window_start_utc,
            self.baseline_window_end_utc,
            "baseline window",
        )
        _validate_time_window(
            self.comparison_window_start_utc,
            self.comparison_window_end_utc,
            "comparison window",
        )
        _validate_optional_nonnegative_decimal(self.drift_score, "drift_score")


def _validate_time_window(start: datetime, end: datetime, field_name: str) -> None:
    start_utc = require_aware_utc_datetime(start)
    end_utc = require_aware_utc_datetime(end)
    if start_utc >= end_utc:
        raise ValueError(f"{field_name} start must be before end")


def _validate_nonnegative_decimal(value: Decimal, field_name: str) -> None:
    if value < 0:
        raise ValueError(f"{field_name} cannot be negative")


def _validate_optional_nonnegative_decimal(value: Decimal | None, field_name: str) -> None:
    if value is not None:
        _validate_nonnegative_decimal(value, field_name)


def _require_non_empty(value: str, field_name: str) -> None:
    if not value:
        raise ValueError(f"{field_name} must be non-empty")


def _require_json_object(value: dict[str, object], field_name: str) -> None:
    if not value:
        raise ValueError(f"{field_name} must be a non-empty JSON object")
