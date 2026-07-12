# M06 Handoff

## Milestone Status

M06 - Alerts, Scenarios, and Briefings is complete on branch `m06`.

## Implemented Decision-Support Capabilities

- deterministic alert severity, type, lifecycle, and evaluation contracts
- high-demand alerts
- ramp alerts
- previous-forecast deviation alerts
- M03 source-health context alerts
- combined context alerts
- deterministic alert fingerprints and duplicate-active alert prevention
- immutable alert evidence persistence
- immutable alert lifecycle history
- deterministic demand-growth scenarios
- deterministic approximate weather-adjustment scenarios
- deterministic combined weather/load scenarios
- persisted scenario assumptions, limitations, summaries, and interval result rows
- deterministic briefing facts from forecasts, peaks, ramps, alerts, source health, scenarios, and known limitations
- backend API outputs for alerts, scenarios, and briefings
- simple standard-library decision runner commands

## Database Tables Added

Chunk 1:

- `alert_evaluation_runs`
- `alerts`
- `alert_evidence`
- `alert_lifecycle_history`

Chunk 2:

- `scenario_runs`
- `scenario_assumptions`
- `scenario_result_rows`
- `briefing_runs`
- `briefing_facts`

## Commands Available

Evaluate alerts:

```powershell
uv run python -m gridops.decision.runner evaluate-alerts --forecast-run-id <forecast_run_id>
```

Run a demand-growth scenario:

```powershell
uv run python -m gridops.decision.runner run-scenario --forecast-run-id <forecast_run_id> --load-growth-percent 2
```

Run a weather-adjustment scenario:

```powershell
uv run python -m gridops.decision.runner run-scenario --forecast-run-id <forecast_run_id> --temperature-delta-c 3
```

Generate briefing facts:

```powershell
uv run python -m gridops.decision.runner generate-briefing --forecast-run-id <forecast_run_id>
```

## Endpoints Available

- `GET /alerts`
- `GET /alerts/{alert_id}`
- `POST /alerts/evaluate`
- `PATCH /alerts/{alert_id}/state`
- `POST /scenarios`
- `GET /scenarios/{scenario_id}`
- `POST /briefings/generate`
- `GET /briefings/latest`

## Alert Rules Implemented

- `high_demand_fixed_threshold`
- `large_adjacent_forecast_ramp`
- `previous_forecast_deviation`
- `source_health_context`
- `combined_forecast_and_source_health_context`

Thresholds are documented in `docs/decision/ALERT_RULES.md`.

## Lifecycle Behavior

Supported states:

- `open`
- `acknowledged`
- `resolved`
- `suppressed`
- `expired`

Valid transitions:

- `open` to `acknowledged`, `resolved`, `suppressed`, or `expired`
- `acknowledged` to `resolved`, `suppressed`, or `expired`

Resolved, suppressed, and expired alerts are terminal.

## Scenario Behavior

- Demand-growth scenarios apply percent growth and added MW to M05 base forecast values.
- Weather-adjustment scenarios apply a documented deterministic approximation of `75.000 MW` per degree C.
- Combined scenarios add the deterministic demand and weather deltas.
- Scenario outputs are simulations, not forecasts.

## Briefing Behavior

Briefings persist deterministic structured facts only. Fact types include:

- forecast issue and horizon
- expected peak
- largest ramp
- open alert summary
- highest attention hours
- source-health summary
- quality limitations
- confidence limitations
- scenario highlights
- known unsupported claims

No free-form or LLM narrative generation is implemented.

## Evidence Behavior

- Alerts preserve current structured evidence and immutable evidence history.
- Alert lifecycle transitions preserve immutable history.
- Scenario runs preserve assumptions, limitations, summaries, interval rows, and source prediction references.
- Briefing facts preserve structured evidence references to source tables or source services.

## Verification Summary

Final M06 verification passed:

- `uv run ruff format .`: `110 files left unchanged`
- `uv run ruff format --check .`: `110 files already formatted`
- `uv run ruff check .`: `All checks passed!`
- `uv run mypy src tests`: `Success: no issues found in 102 source files`
- `uv run pytest -q`: `214 passed, 1 warning in 165776.88s (1 day, 22:02:56)`
- clean Alembic upgrade from empty schema reached `f7a8b9c0d1e2 (head)`

Exact results are in `docs/verification/M06_VERIFICATION.md`.

## Known Limitations

- No true prediction intervals or confidence alerting because M05 does not generate true quantiles.
- Weather scenarios are deterministic approximations, not model recomputation.
- Humidity assumptions are stored but do not affect scenario values.
- No notifications or ticketing.
- No dashboard, deployment, authentication, public demo mode, or release packaging.
- No LLM narrative generation.

## Risks For M07

- M07 should present scenario outputs as simulations, not forecasts.
- M07 should not use alert severities as official IESO emergency or reliability categories.
- M07 should visibly communicate confidence/uncertainty limitations.
- M07 should consume evidence-backed API fields rather than inventing explanatory text.
- M07 should handle empty alert/scenario/briefing states gracefully.

## Exact Recommended Next Step

Begin M07 by building the read-only operational dashboard against the M06 backend outputs, starting with forecast, alert, source-health, scenario, and briefing views. Keep dashboard claims evidence-backed and preserve all M06 limitations in the UI.
