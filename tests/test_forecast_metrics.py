"""Tests for M04 baseline metrics."""

from datetime import UTC, datetime
from decimal import Decimal

from gridops.forecasting.baselines import BaselinePrediction
from gridops.forecasting.metrics import BIAS, MAE, RMSE, WAPE, calculate_baseline_metrics


def test_mae_rmse_wape_and_bias_calculation() -> None:
    """Required aggregate metrics are calculated over usable predictions."""

    predictions = [
        _prediction(Decimal("100.0"), Decimal("90.0")),
        _prediction(Decimal("110.0"), Decimal("100.0")),
    ]

    metrics = {
        metric.metric_name: metric.metric_value
        for metric in calculate_baseline_metrics(predictions)
    }

    assert metrics[MAE] == Decimal("10.0")
    assert metrics[RMSE] == Decimal("10.0")
    assert metrics[WAPE] == Decimal("20.0") / Decimal("190.0")
    assert metrics[BIAS] == Decimal("10.0")


def test_metric_functions_handle_null_and_skipped_predictions() -> None:
    """Skipped/null predictions are ignored safely."""

    predictions = [
        _prediction(Decimal("100.0"), Decimal("90.0")),
        _prediction(None, Decimal("100.0"), status="skipped"),
        _prediction(Decimal("999.0"), None),
    ]

    metrics = calculate_baseline_metrics(predictions)

    assert {metric.metric_name: metric.prediction_count for metric in metrics} == {
        MAE: 1,
        RMSE: 1,
        WAPE: 1,
        BIAS: 1,
    }


def test_wape_handles_zero_denominator_safely() -> None:
    """WAPE is omitted when actual-demand denominator is zero."""

    metrics = calculate_baseline_metrics([_prediction(Decimal("10.0"), Decimal("0.0"))])

    assert WAPE not in {metric.metric_name for metric in metrics}


def _prediction(
    predicted: Decimal | None,
    actual: Decimal | None,
    *,
    status: str = "predicted",
) -> BaselinePrediction:
    return BaselinePrediction(
        baseline_name="same_hour_yesterday",
        forecast_issue_time_utc=datetime(2026, 7, 9, 15, tzinfo=UTC),
        target_interval_start_utc=datetime(2026, 7, 9, 16, tzinfo=UTC),
        target_interval_end_utc=datetime(2026, 7, 9, 17, tzinfo=UTC),
        lead_hour=1,
        predicted_demand_mw=predicted,
        actual_demand_mw=actual,
        prediction_status=status,
    )
