"""Forecasting foundations for GridOps Intelligence M04."""

from gridops.forecasting.horizons import ForecastHorizonTarget, generate_hourly_horizon
from gridops.forecasting.issue_contract import (
    DEFAULT_FORECAST_TYPE,
    DEFAULT_FORECASTING_FEATURE_VERSION,
    DEFAULT_HORIZON_HOURS,
    POINT_IN_TIME_SAFETY_RULE,
    ForecastIssueContract,
)

__all__ = [
    "DEFAULT_FORECASTING_FEATURE_VERSION",
    "DEFAULT_FORECAST_TYPE",
    "DEFAULT_HORIZON_HOURS",
    "POINT_IN_TIME_SAFETY_RULE",
    "ForecastHorizonTarget",
    "ForecastIssueContract",
    "generate_hourly_horizon",
]
