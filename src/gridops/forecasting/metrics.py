"""Baseline forecast metric calculations for M04."""

import math
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from gridops.forecasting.baselines import BaselinePrediction

MAE = "mae"
RMSE = "rmse"
WAPE = "wape"
BIAS = "bias"
METRIC_NAMES = (MAE, RMSE, WAPE, BIAS)


@dataclass(frozen=True, slots=True)
class MetricResult:
    """One aggregate metric result for a baseline."""

    baseline_name: str
    metric_name: str
    metric_value: Decimal
    prediction_count: int


def calculate_baseline_metrics(predictions: Iterable[BaselinePrediction]) -> list[MetricResult]:
    """Calculate MAE, RMSE, WAPE, and bias over usable predictions."""

    usable = _usable_predictions(predictions)
    if not usable:
        return []

    baseline_name = usable[0].baseline_name
    errors = [
        prediction.predicted_demand_mw - prediction.actual_demand_mw
        for prediction in usable
        if prediction.predicted_demand_mw is not None and prediction.actual_demand_mw is not None
    ]
    absolute_errors = [abs(error) for error in errors]
    actual_absolute_sum = sum(
        abs(prediction.actual_demand_mw)
        for prediction in usable
        if prediction.actual_demand_mw is not None
    )
    results = [
        MetricResult(baseline_name, MAE, sum(absolute_errors) / Decimal(len(errors)), len(errors)),
        MetricResult(
            baseline_name,
            RMSE,
            Decimal(str(math.sqrt(float(sum(error * error for error in errors) / len(errors))))),
            len(errors),
        ),
        MetricResult(baseline_name, BIAS, sum(errors) / Decimal(len(errors)), len(errors)),
    ]
    if actual_absolute_sum != 0:
        results.insert(
            2,
            MetricResult(
                baseline_name,
                WAPE,
                sum(absolute_errors) / actual_absolute_sum,
                len(errors),
            ),
        )

    return results


def _usable_predictions(
    predictions: Iterable[BaselinePrediction],
) -> list[BaselinePrediction]:
    return [
        prediction
        for prediction in predictions
        if prediction.prediction_status == "predicted"
        and prediction.predicted_demand_mw is not None
        and prediction.actual_demand_mw is not None
    ]
