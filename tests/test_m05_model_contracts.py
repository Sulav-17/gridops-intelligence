"""Tests for M05 production forecasting typed contracts."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from gridops.forecasting.model_contracts import (
    DriftSummaryContract,
    ForecastPredictionContract,
    ModelSelectionContract,
    ModelSelectionStatus,
    ModelTrainingRunContract,
    ModelTrainingStatus,
    PeakOutputContract,
    PerformanceSummaryContract,
    RampOutputContract,
)


def test_model_training_contract_validates_utc_windows() -> None:
    """Training contracts require ordered timezone-aware UTC windows."""

    contract = ModelTrainingRunContract(
        model_name="candidate_tree",
        model_type="sklearn_random_forest",
        model_version="m05-c01-contract",
        feature_version="m04_c01_foundation",
        status=ModelTrainingStatus.PLANNED,
        training_window_start_utc=datetime(2026, 1, 1, tzinfo=UTC),
        training_window_end_utc=datetime(2026, 2, 1, tzinfo=UTC),
        evaluation_window_start_utc=datetime(2026, 2, 1, tzinfo=UTC),
        evaluation_window_end_utc=datetime(2026, 2, 8, tzinfo=UTC),
        parameters={"max_depth": 4},
        metrics_summary={"mae": 10.5},
    )

    assert contract.status is ModelTrainingStatus.PLANNED
    assert contract.parameters == {"max_depth": 4}

    with pytest.raises(ValueError, match="timezone-aware UTC"):
        ModelTrainingRunContract(
            model_name="candidate_tree",
            model_type="sklearn_random_forest",
            model_version="m05-c01-contract",
            feature_version="m04_c01_foundation",
            status=ModelTrainingStatus.PLANNED,
            training_window_start_utc=datetime(2026, 1, 1),
            training_window_end_utc=datetime(2026, 2, 1, tzinfo=UTC),
            evaluation_window_start_utc=datetime(2026, 2, 1, tzinfo=UTC),
            evaluation_window_end_utc=datetime(2026, 2, 8, tzinfo=UTC),
        )


def test_model_selection_contract_requires_metrics_json_objects() -> None:
    """Selection contracts preserve explicit candidate and baseline metric payloads."""

    selection = ModelSelectionContract(
        model_name="candidate_tree",
        model_type="sklearn_random_forest",
        model_version="m05-c01-contract",
        feature_version="m04_c01_foundation",
        selection_status=ModelSelectionStatus.EVALUATED,
        selection_reason="schema-only contract test",
        candidate_metrics={"mae": 10.0},
        baseline_metrics={"same_hour_yesterday": {"mae": 12.0}},
        training_window_start_utc=datetime(2026, 1, 1, tzinfo=UTC),
        training_window_end_utc=datetime(2026, 2, 1, tzinfo=UTC),
        evaluation_window_start_utc=datetime(2026, 2, 1, tzinfo=UTC),
        evaluation_window_end_utc=datetime(2026, 2, 8, tzinfo=UTC),
    )

    assert selection.selection_status is ModelSelectionStatus.EVALUATED
    assert selection.candidate_metrics["mae"] == 10.0

    with pytest.raises(ValueError, match="candidate_metrics"):
        ModelSelectionContract(
            model_name="candidate_tree",
            model_type="sklearn_random_forest",
            model_version="m05-c01-contract",
            feature_version="m04_c01_foundation",
            selection_status=ModelSelectionStatus.EVALUATED,
            selection_reason="missing metrics",
            candidate_metrics={},
            baseline_metrics={"same_hour_yesterday": {"mae": 12.0}},
            training_window_start_utc=datetime(2026, 1, 1, tzinfo=UTC),
            training_window_end_utc=datetime(2026, 2, 1, tzinfo=UTC),
            evaluation_window_start_utc=datetime(2026, 2, 1, tzinfo=UTC),
            evaluation_window_end_utc=datetime(2026, 2, 8, tzinfo=UTC),
        )


def test_forecast_prediction_contract_allows_nullable_p10_p90() -> None:
    """True quantile modeling can remain deferred while P50 output is required."""

    prediction = ForecastPredictionContract(
        forecast_issue_time_utc=datetime(2026, 2, 8, 15, tzinfo=UTC),
        target_interval_start_utc=datetime(2026, 2, 8, 16, tzinfo=UTC),
        target_interval_end_utc=datetime(2026, 2, 8, 17, tzinfo=UTC),
        lead_hour=1,
        prediction_type="p50_only",
        p50_demand_mw=Decimal("18000.000"),
        p10_demand_mw=None,
        p90_demand_mw=None,
    )

    assert prediction.p50_demand_mw == Decimal("18000.000")
    assert prediction.p10_demand_mw is None
    assert prediction.p90_demand_mw is None

    with pytest.raises(ValueError, match="p50_demand_mw or point_forecast_demand_mw"):
        ForecastPredictionContract(
            forecast_issue_time_utc=datetime(2026, 2, 8, 15, tzinfo=UTC),
            target_interval_start_utc=datetime(2026, 2, 8, 16, tzinfo=UTC),
            target_interval_end_utc=datetime(2026, 2, 8, 17, tzinfo=UTC),
            lead_hour=1,
            prediction_type="missing_point",
        )


def test_forecast_prediction_contract_validates_quantile_order() -> None:
    """Provided quantiles must not contradict the P50 value."""

    with pytest.raises(ValueError, match="p10_demand_mw cannot exceed"):
        ForecastPredictionContract(
            forecast_issue_time_utc=datetime(2026, 2, 8, 15, tzinfo=UTC),
            target_interval_start_utc=datetime(2026, 2, 8, 16, tzinfo=UTC),
            target_interval_end_utc=datetime(2026, 2, 8, 17, tzinfo=UTC),
            lead_hour=1,
            prediction_type="quantile",
            p10_demand_mw=Decimal("18100.000"),
            p50_demand_mw=Decimal("18000.000"),
        )


def test_peak_and_ramp_output_contracts_validate_operational_fields() -> None:
    """Peak and ramp outputs validate intervals, lead hours, and absolute ramp."""

    peak = PeakOutputContract(
        peak_target_interval_start_utc=datetime(2026, 2, 8, 20, tzinfo=UTC),
        peak_target_interval_end_utc=datetime(2026, 2, 8, 21, tzinfo=UTC),
        peak_demand_mw=Decimal("21000.000"),
        peak_lead_hour=5,
    )
    ramp = RampOutputContract(
        target_interval_start_utc=datetime(2026, 2, 8, 21, tzinfo=UTC),
        previous_target_interval_start_utc=datetime(2026, 2, 8, 20, tzinfo=UTC),
        forecast_ramp_mw=Decimal("-350.000"),
        absolute_ramp_mw=Decimal("350.000"),
    )

    assert peak.peak_lead_hour == 5
    assert ramp.absolute_ramp_mw == Decimal("350.000")

    with pytest.raises(ValueError, match="absolute_ramp_mw"):
        RampOutputContract(
            target_interval_start_utc=datetime(2026, 2, 8, 21, tzinfo=UTC),
            previous_target_interval_start_utc=datetime(2026, 2, 8, 20, tzinfo=UTC),
            forecast_ramp_mw=Decimal("-350.000"),
            absolute_ramp_mw=Decimal("349.000"),
        )


def test_performance_and_drift_summary_contracts_validate_counts_and_windows() -> None:
    """Monitoring summary contracts are schema-only and deterministic."""

    performance = PerformanceSummaryContract(
        model_name="candidate_tree",
        model_type="sklearn_random_forest",
        model_version="m05-c01-contract",
        feature_version="m04_c01_foundation",
        metric_name="mae",
        metric_value=Decimal("10.000000"),
        row_count=24,
        evaluation_window_start_utc=datetime(2026, 2, 1, tzinfo=UTC),
        evaluation_window_end_utc=datetime(2026, 2, 2, tzinfo=UTC),
        metric_unit="MW",
    )
    drift = DriftSummaryContract(
        model_name="candidate_tree",
        model_type="sklearn_random_forest",
        model_version="m05-c01-contract",
        feature_version="m04_c01_foundation",
        feature_name="lag_24h_mw",
        drift_metric_name="population_stability_index",
        drift_score=Decimal("0.010000"),
        baseline_window_start_utc=datetime(2026, 1, 1, tzinfo=UTC),
        baseline_window_end_utc=datetime(2026, 2, 1, tzinfo=UTC),
        comparison_window_start_utc=datetime(2026, 2, 1, tzinfo=UTC),
        comparison_window_end_utc=datetime(2026, 2, 8, tzinfo=UTC),
    )

    assert performance.row_count == 24
    assert drift.drift_score == Decimal("0.010000")

    with pytest.raises(ValueError, match="row_count"):
        PerformanceSummaryContract(
            model_name="candidate_tree",
            model_type="sklearn_random_forest",
            model_version="m05-c01-contract",
            feature_version="m04_c01_foundation",
            metric_name="mae",
            metric_value=Decimal("10.000000"),
            row_count=-1,
            evaluation_window_start_utc=datetime(2026, 2, 1, tzinfo=UTC),
            evaluation_window_end_utc=datetime(2026, 2, 1, tzinfo=UTC) + timedelta(days=1),
        )
