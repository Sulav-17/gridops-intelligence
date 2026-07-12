# M06 Scenario Runbook

## Status

This runbook covers the M06 scenario engine. Scenario outputs are decision-support simulations, not production forecasts.

## Supported Scenario Types

- `demand_growth`: applies percent growth and/or added MW load to each base M05 forecast interval.
- `weather_adjustment`: applies a deterministic approximate MW delta from a temperature change assumption.
- `combined_weather_load`: combines the deterministic demand-growth and weather-adjustment deltas.

## Assumptions

Scenario assumptions are explicit and persisted in `scenario_assumptions` and `scenario_runs.assumptions_json`.

Supported assumptions:

- `demand_growth_percent`
- `added_load_mw`
- `temperature_delta_c`
- `humidity_delta_percent`

Humidity deltas are recorded as explicit assumptions, but no humidity response coefficient is implemented in M06.

## Calculation Behavior

Demand growth:

- percent growth is calculated from the base forecast value
- added MW is added after percent growth
- row delta equals percent-growth MW plus added MW

Weather adjustment:

- temperature deltas use a documented approximation of `75.000 MW` per degree C
- the model is not retrained
- M05 forecasts are not recomputed from changed weather features

Combined scenarios:

- demand-growth delta and weather delta are added together
- the result is labelled as a simulation

## API Usage

Generate a scenario:

```powershell
POST /scenarios
```

Example body:

```json
{
  "production_forecast_run_id": 1,
  "scenario_type": "demand_growth",
  "generated_at_utc": "2026-07-10T15:00:00Z",
  "demand_growth_percent": "2.5",
  "added_load_mw": "100.000"
}
```

Fetch a scenario:

```powershell
GET /scenarios/{scenario_id}
```

## Runner Usage

Demand-growth scenario:

```powershell
uv run python -m gridops.decision.runner run-scenario --forecast-run-id <forecast_run_id> --load-growth-percent 2
```

Weather scenario:

```powershell
uv run python -m gridops.decision.runner run-scenario --forecast-run-id <forecast_run_id> --temperature-delta-c 3
```

Combined scenario:

```powershell
uv run python -m gridops.decision.runner run-scenario --forecast-run-id <forecast_run_id> --load-growth-percent 2 --temperature-delta-c 3
```

## Persistence

Tables:

- `scenario_runs`
- `scenario_assumptions`
- `scenario_result_rows`

Every scenario preserves:

- scenario ID
- scenario type
- base production forecast run ID
- assumptions
- generated timestamp UTC
- affected intervals
- base value
- scenario value
- delta
- peak summary
- limitations
- scenario version

## Interpretation

Scenario outputs answer "what if these assumptions were applied to the base forecast values?" They are not official forecasts, do not replace M05 outputs, and do not imply causal attribution.

## Current Limitations

- Weather adjustment is approximate because M05 does not safely recompute forecasts from changed weather features.
- No model retraining or feature-snapshot rebuilding occurs.
- No dashboard or notification behavior is implemented.
