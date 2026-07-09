"""Deterministic forecast horizon generation."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from gridops.forecasting.issue_contract import ForecastIssueContract, require_aware_utc_datetime


@dataclass(frozen=True, slots=True)
class ForecastHorizonTarget:
    """One hourly target interval generated from a forecast issue."""

    forecast_issue_time_utc: datetime
    target_interval_start_utc: datetime
    target_interval_end_utc: datetime
    lead_hour: int
    forecast_type: str
    feature_version: str
    point_in_time_safety_rule: str


def generate_hourly_horizon(contract: ForecastIssueContract) -> list[ForecastHorizonTarget]:
    """Generate the next N ordered hourly target intervals after the issue time."""

    first_start = _next_hour_after(contract.forecast_issue_time_utc)
    targets: list[ForecastHorizonTarget] = []

    for zero_based_index in range(contract.horizon_length_hours):
        start = first_start + timedelta(hours=zero_based_index)
        end = start + timedelta(hours=1)
        targets.append(
            ForecastHorizonTarget(
                forecast_issue_time_utc=contract.forecast_issue_time_utc,
                target_interval_start_utc=start,
                target_interval_end_utc=end,
                lead_hour=zero_based_index + 1,
                forecast_type=contract.forecast_type,
                feature_version=contract.feature_version,
                point_in_time_safety_rule=contract.point_in_time_safety_rule,
            )
        )

    return targets


def _next_hour_after(value: datetime) -> datetime:
    value = require_aware_utc_datetime(value)
    truncated = value.replace(minute=0, second=0, microsecond=0)

    return truncated + timedelta(hours=1)
