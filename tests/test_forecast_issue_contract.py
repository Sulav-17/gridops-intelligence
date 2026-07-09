"""Tests for the M04 forecast issue contract and horizons."""

from datetime import UTC, datetime, timedelta

import pytest

from gridops.forecasting import ForecastIssueContract, generate_hourly_horizon
from gridops.forecasting.issue_contract import DEFAULT_HORIZON_HOURS


def test_forecast_issue_contract_accepts_aware_utc_issue_time() -> None:
    """The contract accepts canonical aware UTC issue timestamps."""

    issue_time = datetime(2026, 7, 9, 15, tzinfo=UTC)

    contract = ForecastIssueContract(forecast_issue_time_utc=issue_time)

    assert contract.forecast_issue_time_utc == issue_time
    assert contract.horizon_length_hours == DEFAULT_HORIZON_HOURS
    assert contract.forecast_type == "day_ahead_hourly_ontario_demand"
    assert contract.feature_version == "m04_c01_foundation"


def test_forecast_issue_contract_rejects_naive_issue_time() -> None:
    """Naive forecast issue timestamps are not accepted."""

    with pytest.raises(ValueError, match="timezone-aware UTC"):
        ForecastIssueContract(forecast_issue_time_utc=datetime(2026, 7, 9, 15))


def test_hourly_horizon_creates_24_ordered_targets_by_default() -> None:
    """Default horizon generation creates the next 24 ordered hourly targets."""

    issue_time = datetime(2026, 7, 9, 15, tzinfo=UTC)
    contract = ForecastIssueContract(forecast_issue_time_utc=issue_time)

    targets = generate_hourly_horizon(contract)

    assert len(targets) == 24
    assert [target.lead_hour for target in targets] == list(range(1, 25))
    assert [target.target_interval_start_utc for target in targets] == sorted(
        target.target_interval_start_utc for target in targets
    )
    assert targets[0].target_interval_start_utc == datetime(2026, 7, 9, 16, tzinfo=UTC)
    assert targets[-1].target_interval_end_utc == datetime(2026, 7, 10, 16, tzinfo=UTC)


def test_hourly_horizon_targets_are_one_hour_and_after_issue_time() -> None:
    """Generated target intervals are hourly and strictly after the issue time."""

    issue_time = datetime(2026, 7, 9, 15, 30, tzinfo=UTC)
    contract = ForecastIssueContract(forecast_issue_time_utc=issue_time)

    targets = generate_hourly_horizon(contract)

    for target in targets:
        assert target.target_interval_start_utc > issue_time
        assert target.target_interval_end_utc - target.target_interval_start_utc == timedelta(
            hours=1
        )
        assert target.forecast_issue_time_utc == issue_time
        assert target.forecast_type == contract.forecast_type
        assert target.feature_version == contract.feature_version
