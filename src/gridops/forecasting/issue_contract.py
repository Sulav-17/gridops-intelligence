"""Forecast issue contract for deterministic M04 evaluation rows."""

from dataclasses import dataclass
from datetime import UTC, datetime

DEFAULT_FORECAST_TYPE = "day_ahead_hourly_ontario_demand"
DEFAULT_FORECASTING_FEATURE_VERSION = "m04_c01_foundation"
DEFAULT_HORIZON_HOURS = 24
POINT_IN_TIME_SAFETY_RULE = "features_must_be_available_at_or_before_forecast_issue_time_utc"


@dataclass(frozen=True, slots=True)
class ForecastIssueContract:
    """Define one configurable forecast issue and its leakage-safety metadata.

    The exact operational issuance convention is not fixed in M04-C01. Callers
    must provide an aware UTC issue time; later M04 chunks can choose concrete
    schedules without changing the target-row contract.
    """

    forecast_issue_time_utc: datetime
    horizon_length_hours: int = DEFAULT_HORIZON_HOURS
    forecast_type: str = DEFAULT_FORECAST_TYPE
    feature_version: str = DEFAULT_FORECASTING_FEATURE_VERSION
    point_in_time_safety_rule: str = POINT_IN_TIME_SAFETY_RULE

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "forecast_issue_time_utc",
            require_aware_utc_datetime(self.forecast_issue_time_utc),
        )
        if self.horizon_length_hours <= 0:
            raise ValueError("horizon_length_hours must be positive")
        if not self.forecast_type:
            raise ValueError("forecast_type must be non-empty")
        if not self.feature_version:
            raise ValueError("feature_version must be non-empty")
        if not self.point_in_time_safety_rule:
            raise ValueError("point_in_time_safety_rule must be non-empty")


def require_aware_utc_datetime(value: datetime) -> datetime:
    """Return a timezone-aware UTC datetime or reject unsafe input."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware UTC")
    if value.utcoffset() != UTC.utcoffset(value):
        raise ValueError("datetime must be UTC")

    return value.astimezone(UTC)
