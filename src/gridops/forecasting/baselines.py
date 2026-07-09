"""Deterministic M04 baseline forecast models."""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from gridops.forecasting.issue_contract import require_aware_utc_datetime
from gridops.models import FeatureSnapshotRow, IesoHourlyDemand

SAME_HOUR_YESTERDAY = "same_hour_yesterday"
SAME_HOUR_LAST_WEEK = "same_hour_last_week"
SEASONAL_HOURLY_MEAN = "seasonal_hourly_mean"
RIDGE = "ridge"
BASELINE_NAMES = (SAME_HOUR_YESTERDAY, SAME_HOUR_LAST_WEEK, SEASONAL_HOURLY_MEAN, RIDGE)


@dataclass(frozen=True, slots=True)
class BaselinePrediction:
    """One baseline prediction for one target interval."""

    baseline_name: str
    forecast_issue_time_utc: datetime
    target_interval_start_utc: datetime
    target_interval_end_utc: datetime
    lead_hour: int
    predicted_demand_mw: Decimal | None
    actual_demand_mw: Decimal | None
    prediction_status: str
    feature_snapshot_row_id: int | None = None
    lineage_metadata: str | None = None


@dataclass(frozen=True, slots=True)
class RidgeTrainingRow:
    """One point-in-time feature row with an after-the-fact training target."""

    feature_snapshot_row_id: int | None
    forecast_issue_time_utc: datetime
    target_interval_start_utc: datetime
    target_interval_end_utc: datetime
    lead_hour: int
    feature_payload: dict[str, object]
    actual_demand_mw: Decimal | None


def predict_same_hour_yesterday(
    *,
    forecast_issue_time_utc: datetime,
    target_interval_start_utc: datetime,
    target_interval_end_utc: datetime,
    lead_hour: int,
    demand_history: Sequence[IesoHourlyDemand],
    actual_demand_mw: Decimal | None = None,
) -> BaselinePrediction:
    """Predict from the current demand row 24 hours before the target start."""

    return _predict_lag_baseline(
        baseline_name=SAME_HOUR_YESTERDAY,
        lag=timedelta(hours=24),
        forecast_issue_time_utc=forecast_issue_time_utc,
        target_interval_start_utc=target_interval_start_utc,
        target_interval_end_utc=target_interval_end_utc,
        lead_hour=lead_hour,
        demand_history=demand_history,
        actual_demand_mw=actual_demand_mw,
    )


def predict_same_hour_last_week(
    *,
    forecast_issue_time_utc: datetime,
    target_interval_start_utc: datetime,
    target_interval_end_utc: datetime,
    lead_hour: int,
    demand_history: Sequence[IesoHourlyDemand],
    actual_demand_mw: Decimal | None = None,
) -> BaselinePrediction:
    """Predict from the current demand row 168 hours before the target start."""

    return _predict_lag_baseline(
        baseline_name=SAME_HOUR_LAST_WEEK,
        lag=timedelta(hours=168),
        forecast_issue_time_utc=forecast_issue_time_utc,
        target_interval_start_utc=target_interval_start_utc,
        target_interval_end_utc=target_interval_end_utc,
        lead_hour=lead_hour,
        demand_history=demand_history,
        actual_demand_mw=actual_demand_mw,
    )


def predict_seasonal_hourly_mean(
    *,
    forecast_issue_time_utc: datetime,
    target_interval_start_utc: datetime,
    target_interval_end_utc: datetime,
    lead_hour: int,
    training_window_start_utc: datetime,
    training_window_end_utc: datetime,
    demand_history: Sequence[IesoHourlyDemand],
    actual_demand_mw: Decimal | None = None,
) -> BaselinePrediction:
    """Predict from the mean historical demand for the target UTC hour."""

    issue_time = require_aware_utc_datetime(forecast_issue_time_utc)
    target_start = require_aware_utc_datetime(target_interval_start_utc)
    target_end = require_aware_utc_datetime(target_interval_end_utc)
    train_start = require_aware_utc_datetime(training_window_start_utc)
    train_end = require_aware_utc_datetime(training_window_end_utc)
    values = [
        row.demand_mw
        for row in demand_history
        if row.is_current
        and row.interval_start_utc >= train_start
        and row.interval_end_utc <= train_end
        and row.interval_end_utc <= issue_time
        and row.interval_start_utc.hour == target_start.hour
    ]
    prediction = (sum(values) / Decimal(len(values))) if values else None

    return BaselinePrediction(
        baseline_name=SEASONAL_HOURLY_MEAN,
        forecast_issue_time_utc=issue_time,
        target_interval_start_utc=target_start,
        target_interval_end_utc=target_end,
        lead_hour=lead_hour,
        predicted_demand_mw=prediction,
        actual_demand_mw=actual_demand_mw,
        prediction_status="predicted" if prediction is not None else "skipped",
        lineage_metadata=json.dumps(
            {
                "training_window_start_utc": train_start.isoformat(),
                "training_window_end_utc": train_end.isoformat(),
                "grouping": "target_hour_utc",
                "training_row_count": len(values),
            },
            sort_keys=True,
        ),
    )


class RidgeBaseline:
    """Simple deterministic Ridge baseline for M04 evaluation."""

    baseline_name = RIDGE

    def __init__(self) -> None:
        self._pipeline: object | None = None
        self.training_row_count = 0

    def fit(
        self,
        rows: Sequence[RidgeTrainingRow],
        *,
        training_window_start_utc: datetime,
        training_window_end_utc: datetime,
    ) -> None:
        """Fit Ridge using only rows inside the provided time-based training window."""

        train_start = require_aware_utc_datetime(training_window_start_utc)
        train_end = require_aware_utc_datetime(training_window_end_utc)
        training_rows = [
            row
            for row in rows
            if row.actual_demand_mw is not None
            and row.target_interval_start_utc >= train_start
            and row.target_interval_end_utc <= train_end
        ]
        matrix = [_feature_vector(row.feature_payload) for row in training_rows]
        usable = [
            (features, row.actual_demand_mw)
            for features, row in zip(matrix, training_rows, strict=True)
            if features is not None and row.actual_demand_mw is not None
        ]
        self.training_row_count = len(usable)
        if not usable:
            self._pipeline = None
            return

        from sklearn.linear_model import Ridge  # type: ignore[import-untyped]
        from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
        from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

        x_values = [features for features, _ in usable]
        y_values = [float(actual) for _, actual in usable]
        pipeline = Pipeline(
            [
                ("scaler", StandardScaler()),
                ("ridge", Ridge(alpha=1.0)),
            ]
        )
        pipeline.fit(x_values, y_values)
        self._pipeline = pipeline

    def predict(self, row: RidgeTrainingRow) -> BaselinePrediction:
        """Predict one row, returning skipped when features/model are unavailable."""

        feature_vector = _feature_vector(row.feature_payload)
        if self._pipeline is None or feature_vector is None:
            prediction = None
        else:
            raw_prediction = self._pipeline.predict([feature_vector])[0]  # type: ignore[attr-defined]
            prediction = Decimal(str(raw_prediction))

        return BaselinePrediction(
            baseline_name=RIDGE,
            forecast_issue_time_utc=require_aware_utc_datetime(row.forecast_issue_time_utc),
            target_interval_start_utc=require_aware_utc_datetime(row.target_interval_start_utc),
            target_interval_end_utc=require_aware_utc_datetime(row.target_interval_end_utc),
            lead_hour=row.lead_hour,
            predicted_demand_mw=prediction,
            actual_demand_mw=row.actual_demand_mw,
            prediction_status="predicted" if prediction is not None else "skipped",
            feature_snapshot_row_id=row.feature_snapshot_row_id,
            lineage_metadata=json.dumps(
                {
                    "baseline_name": RIDGE,
                    "training_row_count": self.training_row_count,
                    "feature_snapshot_row_id": row.feature_snapshot_row_id,
                },
                sort_keys=True,
            ),
        )


def ridge_training_row_from_snapshot(
    row: FeatureSnapshotRow,
    *,
    actual_demand_mw: Decimal | None,
) -> RidgeTrainingRow:
    """Create a Ridge training row from a persisted feature snapshot row."""

    return RidgeTrainingRow(
        feature_snapshot_row_id=row.id,
        forecast_issue_time_utc=row.forecast_issue_time_utc,
        target_interval_start_utc=row.target_interval_start_utc,
        target_interval_end_utc=row.target_interval_end_utc,
        lead_hour=row.lead_hour,
        feature_payload=json.loads(row.lineage_metadata or "{}"),
        actual_demand_mw=actual_demand_mw,
    )


def _predict_lag_baseline(
    *,
    baseline_name: str,
    lag: timedelta,
    forecast_issue_time_utc: datetime,
    target_interval_start_utc: datetime,
    target_interval_end_utc: datetime,
    lead_hour: int,
    demand_history: Sequence[IesoHourlyDemand],
    actual_demand_mw: Decimal | None,
) -> BaselinePrediction:
    issue_time = require_aware_utc_datetime(forecast_issue_time_utc)
    target_start = require_aware_utc_datetime(target_interval_start_utc)
    target_end = require_aware_utc_datetime(target_interval_end_utc)
    source_start = target_start - lag
    source_row = next(
        (
            row
            for row in demand_history
            if row.is_current
            and row.interval_start_utc == source_start
            and row.interval_end_utc <= issue_time
        ),
        None,
    )

    return BaselinePrediction(
        baseline_name=baseline_name,
        forecast_issue_time_utc=issue_time,
        target_interval_start_utc=target_start,
        target_interval_end_utc=target_end,
        lead_hour=lead_hour,
        predicted_demand_mw=source_row.demand_mw if source_row is not None else None,
        actual_demand_mw=actual_demand_mw,
        prediction_status="predicted" if source_row is not None else "skipped",
        lineage_metadata=json.dumps(
            {
                "lag_hours": int(lag.total_seconds() // 3600),
                "source_demand_row_id": source_row.id if source_row is not None else None,
            },
            sort_keys=True,
        ),
    )


def _feature_vector(payload: dict[str, object]) -> list[float] | None:
    calendar = payload.get("calendar")
    demand = payload.get("demand")
    if not isinstance(calendar, dict) or not isinstance(demand, dict):
        return None

    raw_values = [
        calendar.get("target_hour_utc"),
        calendar.get("day_of_week"),
        calendar.get("month"),
        1 if calendar.get("is_weekend") else 0,
        calendar.get("hour_sin"),
        calendar.get("hour_cos"),
        demand.get("lag_1h_mw"),
        demand.get("lag_2h_mw"),
        demand.get("lag_24h_mw"),
        demand.get("lag_48h_mw"),
        demand.get("lag_168h_mw"),
        demand.get("rolling_mean_mw"),
        demand.get("rolling_min_mw"),
        demand.get("rolling_max_mw"),
        demand.get("rolling_std_mw"),
        demand.get("recent_ramp_mw"),
    ]
    if any(value is None for value in raw_values):
        return None

    return [float(value) for value in raw_values if value is not None]
