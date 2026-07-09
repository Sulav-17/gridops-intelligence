"""Tests for M04 baseline forecast models."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from gridops.forecasting.baselines import (
    RidgeBaseline,
    RidgeTrainingRow,
    predict_same_hour_last_week,
    predict_same_hour_yesterday,
    predict_seasonal_hourly_mean,
)
from gridops.models import IesoHourlyDemand


def test_same_hour_yesterday_baseline_returns_correct_historical_value() -> None:
    """Same-hour-yesterday uses the demand row 24 hours before target."""

    prediction = predict_same_hour_yesterday(
        forecast_issue_time_utc=datetime(2026, 7, 9, 15, tzinfo=UTC),
        target_interval_start_utc=datetime(2026, 7, 9, 16, tzinfo=UTC),
        target_interval_end_utc=datetime(2026, 7, 9, 17, tzinfo=UTC),
        lead_hour=1,
        demand_history=[
            _demand_row(1, datetime(2026, 7, 8, 16, tzinfo=UTC), Decimal("123.0")),
        ],
        actual_demand_mw=Decimal("130.0"),
    )

    assert prediction.predicted_demand_mw == Decimal("123.0")
    assert prediction.actual_demand_mw == Decimal("130.0")
    assert prediction.prediction_status == "predicted"


def test_same_hour_yesterday_does_not_use_target_or_future_actual() -> None:
    """Target and future demand rows are not valid lag sources."""

    prediction = predict_same_hour_yesterday(
        forecast_issue_time_utc=datetime(2026, 7, 9, 15, tzinfo=UTC),
        target_interval_start_utc=datetime(2026, 7, 9, 16, tzinfo=UTC),
        target_interval_end_utc=datetime(2026, 7, 9, 17, tzinfo=UTC),
        lead_hour=1,
        demand_history=[
            _demand_row(1, datetime(2026, 7, 9, 16, tzinfo=UTC), Decimal("999.0")),
            _demand_row(2, datetime(2026, 7, 9, 17, tzinfo=UTC), Decimal("1000.0")),
        ],
        actual_demand_mw=Decimal("999.0"),
    )

    assert prediction.predicted_demand_mw is None
    assert prediction.prediction_status == "skipped"


def test_same_hour_last_week_baseline_returns_correct_historical_value() -> None:
    """Same-hour-last-week uses the demand row 168 hours before target."""

    prediction = predict_same_hour_last_week(
        forecast_issue_time_utc=datetime(2026, 7, 9, 15, tzinfo=UTC),
        target_interval_start_utc=datetime(2026, 7, 9, 16, tzinfo=UTC),
        target_interval_end_utc=datetime(2026, 7, 9, 17, tzinfo=UTC),
        lead_hour=1,
        demand_history=[
            _demand_row(1, datetime(2026, 7, 2, 16, tzinfo=UTC), Decimal("111.0")),
        ],
    )

    assert prediction.predicted_demand_mw == Decimal("111.0")
    assert prediction.prediction_status == "predicted"


def test_seasonal_hourly_mean_uses_only_training_window_data() -> None:
    """Seasonal hourly mean ignores rows outside the time-based training window."""

    prediction = predict_seasonal_hourly_mean(
        forecast_issue_time_utc=datetime(2026, 7, 9, 15, tzinfo=UTC),
        target_interval_start_utc=datetime(2026, 7, 9, 16, tzinfo=UTC),
        target_interval_end_utc=datetime(2026, 7, 9, 17, tzinfo=UTC),
        lead_hour=1,
        training_window_start_utc=datetime(2026, 7, 1, tzinfo=UTC),
        training_window_end_utc=datetime(2026, 7, 9, 15, tzinfo=UTC),
        demand_history=[
            _demand_row(1, datetime(2026, 7, 1, 16, tzinfo=UTC), Decimal("100.0")),
            _demand_row(2, datetime(2026, 7, 2, 16, tzinfo=UTC), Decimal("120.0")),
            _demand_row(3, datetime(2026, 6, 30, 16, tzinfo=UTC), Decimal("999.0")),
            _demand_row(4, datetime(2026, 7, 9, 16, tzinfo=UTC), Decimal("1000.0")),
        ],
    )

    assert prediction.predicted_demand_mw == Decimal("110.0")


def test_missing_history_produces_skipped_prediction() -> None:
    """Missing lag history produces a skipped prediction rather than an invented value."""

    prediction = predict_same_hour_last_week(
        forecast_issue_time_utc=datetime(2026, 7, 9, 15, tzinfo=UTC),
        target_interval_start_utc=datetime(2026, 7, 9, 16, tzinfo=UTC),
        target_interval_end_utc=datetime(2026, 7, 9, 17, tzinfo=UTC),
        lead_hour=1,
        demand_history=[],
    )

    assert prediction.predicted_demand_mw is None
    assert prediction.prediction_status == "skipped"


def test_ridge_trains_with_time_based_training_rows_only() -> None:
    """Ridge fits only rows inside the provided training window."""

    model = RidgeBaseline()
    rows = [
        _ridge_row(datetime(2026, 7, 1, 1, tzinfo=UTC), Decimal("100.0")),
        _ridge_row(datetime(2026, 7, 1, 2, tzinfo=UTC), Decimal("110.0")),
        _ridge_row(datetime(2026, 7, 9, 16, tzinfo=UTC), Decimal("999.0")),
    ]

    model.fit(
        rows,
        training_window_start_utc=datetime(2026, 7, 1, tzinfo=UTC),
        training_window_end_utc=datetime(2026, 7, 2, tzinfo=UTC),
    )
    prediction = model.predict(_ridge_row(datetime(2026, 7, 2, 1, tzinfo=UTC), None))

    assert model.training_row_count == 2
    assert prediction.prediction_status == "predicted"
    assert prediction.predicted_demand_mw is not None


def test_ridge_does_not_use_random_split() -> None:
    """Ridge baseline implementation does not introduce random splitting."""

    source = (
        Path(__file__).resolve().parents[1] / "src" / "gridops" / "forecasting" / "baselines.py"
    ).read_text(encoding="utf-8")

    assert "train_test_split" not in source
    assert "random_split" not in source


def test_ridge_missing_features_produce_skipped_prediction() -> None:
    """Rows with missing feature payloads are skipped safely."""

    model = RidgeBaseline()
    row = RidgeTrainingRow(
        feature_snapshot_row_id=None,
        forecast_issue_time_utc=datetime(2026, 7, 2, tzinfo=UTC),
        target_interval_start_utc=datetime(2026, 7, 2, 1, tzinfo=UTC),
        target_interval_end_utc=datetime(2026, 7, 2, 2, tzinfo=UTC),
        lead_hour=1,
        feature_payload={},
        actual_demand_mw=Decimal("100.0"),
    )

    prediction = model.predict(row)

    assert prediction.prediction_status == "skipped"
    assert prediction.predicted_demand_mw is None


def _demand_row(row_id: int, interval_start_utc: datetime, demand_mw: Decimal) -> IesoHourlyDemand:
    return IesoHourlyDemand(
        id=row_id,
        source_service_date=date(2026, 7, 9),
        source_hour_ending=min(row_id, 24),
        interval_start_utc=interval_start_utc,
        interval_end_utc=interval_start_utc + timedelta(hours=1),
        demand_mw=demand_mw,
        source_snapshot_id=1,
        ingestion_run_id=1,
        row_hash_sha256=str(row_id).zfill(64),
        is_current=True,
        superseded_at_utc=None,
    )


def _ridge_row(target_start: datetime, actual: Decimal | None) -> RidgeTrainingRow:
    payload = {
        "calendar": {
            "target_hour_utc": target_start.hour,
            "day_of_week": target_start.weekday(),
            "month": target_start.month,
            "is_weekend": target_start.weekday() >= 5,
            "hour_sin": 0.0,
            "hour_cos": 1.0,
        },
        "demand": {
            "lag_1h_mw": "100.0",
            "lag_2h_mw": "99.0",
            "lag_24h_mw": "98.0",
            "lag_48h_mw": "97.0",
            "lag_168h_mw": "96.0",
            "rolling_mean_mw": "100.0",
            "rolling_min_mw": "90.0",
            "rolling_max_mw": "110.0",
            "rolling_std_mw": "5.0",
            "recent_ramp_mw": "1.0",
        },
    }
    return RidgeTrainingRow(
        feature_snapshot_row_id=None,
        forecast_issue_time_utc=target_start - timedelta(hours=1),
        target_interval_start_utc=target_start,
        target_interval_end_utc=target_start + timedelta(hours=1),
        lead_hour=1,
        feature_payload=payload,
        actual_demand_mw=actual,
    )
