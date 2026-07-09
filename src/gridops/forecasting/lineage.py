"""Typed lineage structures for M04 forecasting evaluation artifacts."""

from dataclasses import dataclass
from datetime import datetime

from gridops.forecasting.issue_contract import require_aware_utc_datetime


@dataclass(frozen=True, slots=True)
class ForecastLineageReference:
    """Reference to source or quality evidence used by a forecasting artifact."""

    reference_type: str
    reference_id: int

    def __post_init__(self) -> None:
        if not self.reference_type:
            raise ValueError("reference_type must be non-empty")
        if self.reference_id <= 0:
            raise ValueError("reference_id must be positive")


@dataclass(frozen=True, slots=True)
class ForecastLineageSummary:
    """Minimal lineage summary shared by later M04 chunks."""

    forecast_issue_time_utc: datetime
    feature_version: str
    quality_status: str
    references: tuple[ForecastLineageReference, ...] = ()

    def __post_init__(self) -> None:
        require_aware_utc_datetime(self.forecast_issue_time_utc)
        if not self.feature_version:
            raise ValueError("feature_version must be non-empty")
        if not self.quality_status:
            raise ValueError("quality_status must be non-empty")
