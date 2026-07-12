"""Typed M06 scenario contracts."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class ScenarioType(StrEnum):
    """Supported deterministic scenario categories."""

    WEATHER_ADJUSTMENT = "weather_adjustment"
    DEMAND_GROWTH = "demand_growth"
    COMBINED_WEATHER_LOAD = "combined_weather_load"


class ScenarioStatus(StrEnum):
    """Persistence status for scenario runs."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"


SCENARIO_VERSION = "m06_c02_scenario_v1"
WEATHER_TEMPERATURE_DELTA_MW_PER_C = Decimal("75.000")


@dataclass(frozen=True, slots=True)
class ScenarioRequest:
    """Explicit scenario assumptions supplied by a caller."""

    production_forecast_run_id: int
    scenario_type: ScenarioType
    generated_at_utc: datetime
    demand_growth_percent: Decimal | None = None
    added_load_mw: Decimal | None = None
    temperature_delta_c: Decimal | None = None
    humidity_delta_percent: Decimal | None = None


@dataclass(frozen=True, slots=True)
class ScenarioIntervalResult:
    """One deterministic scenario result for a target interval."""

    production_forecast_prediction_id: int | None
    target_interval_start_utc: datetime
    target_interval_end_utc: datetime
    base_value_mw: Decimal
    scenario_value_mw: Decimal
    delta_mw: Decimal
    row_metadata: dict[str, object]
