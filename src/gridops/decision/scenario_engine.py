"""Deterministic M06 scenario calculations and persistence."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from gridops.decision.evidence import normalize_evidence, utc_timestamp
from gridops.decision.scenario_schemas import (
    SCENARIO_VERSION,
    WEATHER_TEMPERATURE_DELTA_MW_PER_C,
    ScenarioIntervalResult,
    ScenarioRequest,
    ScenarioStatus,
    ScenarioType,
)
from gridops.models import (
    ProductionForecastPrediction,
    ProductionForecastRun,
    ScenarioAssumption,
    ScenarioResultRow,
    ScenarioRun,
)

MW_QUANT = Decimal("0.001")


@dataclass(frozen=True, slots=True)
class PersistedScenarioResult:
    """Persisted scenario run and interval rows."""

    scenario_run: ScenarioRun
    result_rows: tuple[ScenarioResultRow, ...]


def run_scenario(
    session: Session,
    *,
    request: ScenarioRequest,
) -> PersistedScenarioResult:
    """Calculate and persist a deterministic scenario."""

    generated_at = utc_timestamp(request.generated_at_utc)
    forecast_run = _require_forecast_run(session, request.production_forecast_run_id)
    predictions = _forecast_predictions(session, forecast_run.id)
    if not predictions:
        raise ValueError("base forecast run has no predictions")

    assumptions = _assumptions(request)
    limitations = _limitations(request)
    interval_results = _calculate_rows(request, predictions)
    summary = _summary(interval_results, assumptions, limitations)

    scenario_run = ScenarioRun(
        scenario_type=request.scenario_type.value,
        production_forecast_run_id=forecast_run.id,
        status=ScenarioStatus.SUCCEEDED.value,
        scenario_version=SCENARIO_VERSION,
        generated_at_utc=generated_at,
        assumptions_json=_json_dict(cast(dict[str, object], assumptions)),
        limitations_json=_json_dict(limitations),
        summary_json=_json_dict(summary),
    )
    session.add(scenario_run)
    session.flush()

    for name, value in assumptions.items():
        assumption = ScenarioAssumption(
            scenario_run_id=scenario_run.id,
            assumption_name=name,
            assumption_value=str(value["value"]),
            assumption_unit=_string_or_none(value.get("unit")),
            assumption_json=_json_dict(value),
        )
        session.add(assumption)

    result_rows = []
    for result in interval_results:
        row = ScenarioResultRow(
            scenario_run_id=scenario_run.id,
            production_forecast_prediction_id=result.production_forecast_prediction_id,
            target_interval_start_utc=result.target_interval_start_utc,
            target_interval_end_utc=result.target_interval_end_utc,
            base_value_mw=result.base_value_mw,
            scenario_value_mw=result.scenario_value_mw,
            delta_mw=result.delta_mw,
            row_metadata_json=_json_dict(result.row_metadata),
        )
        session.add(row)
        result_rows.append(row)
    session.flush()

    return PersistedScenarioResult(scenario_run=scenario_run, result_rows=tuple(result_rows))


def get_scenario(session: Session, scenario_id: int) -> ScenarioRun | None:
    """Return one persisted scenario run."""

    return session.get(ScenarioRun, scenario_id)


def _calculate_rows(
    request: ScenarioRequest,
    predictions: list[ProductionForecastPrediction],
) -> tuple[ScenarioIntervalResult, ...]:
    rows = []
    for prediction in predictions:
        base_value = _forecast_value(prediction)
        if base_value is None:
            continue
        demand_delta = _demand_delta(request, base_value)
        weather_delta = _weather_delta(request)
        delta = _quantize(demand_delta + weather_delta)
        scenario_value = _quantize(base_value + delta)
        rows.append(
            ScenarioIntervalResult(
                production_forecast_prediction_id=prediction.id,
                target_interval_start_utc=prediction.target_interval_start_utc,
                target_interval_end_utc=prediction.target_interval_end_utc,
                base_value_mw=base_value,
                scenario_value_mw=scenario_value,
                delta_mw=delta,
                row_metadata={
                    "base_prediction_source": "production_forecast_predictions",
                    "scenario_output_type": "decision_support_simulation_not_prediction",
                    "demand_delta_mw": demand_delta,
                    "weather_delta_mw": weather_delta,
                    "calculation_version": SCENARIO_VERSION,
                },
            )
        )
    return tuple(rows)


def _demand_delta(request: ScenarioRequest, base_value: Decimal) -> Decimal:
    percent = request.demand_growth_percent or Decimal("0")
    added = request.added_load_mw or Decimal("0")
    return _quantize((base_value * percent / Decimal("100")) + added)


def _weather_delta(request: ScenarioRequest) -> Decimal:
    if request.temperature_delta_c is None:
        return Decimal("0.000")
    return _quantize(request.temperature_delta_c * WEATHER_TEMPERATURE_DELTA_MW_PER_C)


def _assumptions(request: ScenarioRequest) -> dict[str, dict[str, object]]:
    values: dict[str, dict[str, object]] = {
        "scenario_type": {"value": request.scenario_type.value, "unit": None},
    }
    if request.demand_growth_percent is not None:
        values["demand_growth_percent"] = {
            "value": request.demand_growth_percent,
            "unit": "percent",
        }
    if request.added_load_mw is not None:
        values["added_load_mw"] = {"value": request.added_load_mw, "unit": "MW"}
    if request.temperature_delta_c is not None:
        values["temperature_delta_c"] = {"value": request.temperature_delta_c, "unit": "C"}
        values["weather_delta_mw_per_c"] = {
            "value": WEATHER_TEMPERATURE_DELTA_MW_PER_C,
            "unit": "MW_per_C",
        }
    if request.humidity_delta_percent is not None:
        values["humidity_delta_percent"] = {
            "value": request.humidity_delta_percent,
            "unit": "percent",
        }
    return values


def _limitations(request: ScenarioRequest) -> dict[str, object]:
    limitations: dict[str, object] = {
        "scenario_outputs_are_predictions": False,
        "does_not_retrain_model": True,
        "does_not_replace_m05_forecast": True,
    }
    if request.scenario_type in {
        ScenarioType.WEATHER_ADJUSTMENT,
        ScenarioType.COMBINED_WEATHER_LOAD,
    }:
        limitations["weather_adjustment_method"] = (
            "deterministic approximate delta; M05 does not safely recompute forecasts "
            "from changed weather features"
        )
    if request.humidity_delta_percent is not None:
        limitations["humidity_delta_behavior"] = (
            "recorded as an explicit assumption only; no humidity response coefficient "
            "is implemented in this chunk"
        )
    return limitations


def _summary(
    interval_results: tuple[ScenarioIntervalResult, ...],
    assumptions: dict[str, dict[str, object]],
    limitations: dict[str, object],
) -> dict[str, object]:
    if not interval_results:
        return {
            "row_count": 0,
            "assumptions": cast(dict[str, object], assumptions),
            "limitations": limitations,
        }
    base_peak = max(interval_results, key=lambda row: row.base_value_mw)
    scenario_peak = max(interval_results, key=lambda row: row.scenario_value_mw)
    return {
        "row_count": len(interval_results),
        "base_peak_demand_mw": base_peak.base_value_mw,
        "scenario_peak_demand_mw": scenario_peak.scenario_value_mw,
        "peak_delta_mw": _quantize(scenario_peak.scenario_value_mw - base_peak.base_value_mw),
        "scenario_peak_target_interval_start_utc": scenario_peak.target_interval_start_utc,
        "total_delta_mw": _quantize(sum((row.delta_mw for row in interval_results), Decimal("0"))),
        "assumptions": cast(dict[str, object], assumptions),
        "limitations": limitations,
    }


def _forecast_predictions(
    session: Session,
    production_forecast_run_id: int,
) -> list[ProductionForecastPrediction]:
    return list(
        session.scalars(
            select(ProductionForecastPrediction)
            .where(
                ProductionForecastPrediction.production_forecast_run_id
                == production_forecast_run_id
            )
            .order_by(ProductionForecastPrediction.target_interval_start_utc)
        ).all()
    )


def _require_forecast_run(
    session: Session,
    production_forecast_run_id: int,
) -> ProductionForecastRun:
    forecast_run = session.get(ProductionForecastRun, production_forecast_run_id)
    if forecast_run is None:
        raise ValueError(f"production forecast run {production_forecast_run_id} does not exist")
    if forecast_run.status != "succeeded":
        raise ValueError(f"production forecast run is not succeeded: {forecast_run.status}")
    return forecast_run


def _forecast_value(prediction: ProductionForecastPrediction) -> Decimal | None:
    return prediction.p50_demand_mw or prediction.point_forecast_demand_mw


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(MW_QUANT, rounding=ROUND_HALF_UP)


def _json_dict(value: dict[str, object]) -> dict[str, object]:
    normalized = normalize_evidence(value)
    if not isinstance(normalized, dict):
        raise ValueError("normalized scenario payload must be a mapping")
    return normalized


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def utc_now() -> datetime:
    """Return current aware UTC timestamp."""

    return datetime.now(UTC)
