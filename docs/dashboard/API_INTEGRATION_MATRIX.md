# Dashboard API Integration Matrix

## Contract Scope

M07-C01 exposes a compact integration surface over persisted M03-M06 evidence. Dashboard routes serialize records and call existing services; they do not recalculate forecasts, metrics, alerts, scenarios, quality results, or briefings.

| Dashboard screen | Required data | Existing service or endpoint | Response schema | Missing fields | Integration action | Demo-mode behavior | Verified limitation |
|---|---|---|---|---|---|---|---|
| Overview | Latest forecast, peak, ramps, active alert count/severity, source health, latest briefing | M05 tables; M03 `summarize_source_health`; M06 persisted alerts/briefing | `GET /dashboard/overview` | No presentation narrative | Added read-only aggregate adapter | Read-only and available | Forecast may be absent; briefing may be absent; P10/P90 may be null |
| Forecast list/latest | Latest successful production forecast identity and horizon | M05 production forecast tables | `GET /forecasts/latest` | No prior-run list in C01 | Added latest-run read | Read-only and available | Returns 404 when no successful run exists |
| Forecast detail | Run/model identity, hourly P50, nullable P10/P90, actuals, peak, ramps, quality | M05 production forecast, peak, ramp tables; M02 current demand actuals | `GET /forecasts/{forecast_run_id}` | No quantile synthesis; no confidence score | Added persisted-field serializer and actual-demand join | Read-only and available | True prediction intervals are not guaranteed; actuals can be null |
| Alerts | Current and historical alerts with evidence summary | `GET /alerts` | Existing M06 JSON response | No server pagination/filter contract | Reuse existing endpoint | Read-only endpoint remains available | Severities are project attention signals, not official IESO categories |
| Alert detail | Immutable evidence and lifecycle history | `GET /alerts/{alert_id}` | Existing M06 JSON response | None required for C02 | Reuse existing endpoint | Read-only endpoint remains available | Evidence is deterministic and limited to persisted rule inputs |
| Alert mutation | Evaluation and lifecycle transition | `POST /alerts/evaluate`; `PATCH /alerts/{alert_id}/state` | Existing M06 JSON response | Public authentication does not exist | Preserve for trusted mode; block in demo mode | Both return 403 | Demo mode is a product safety boundary, not an authentication system |
| Data quality | Latest dataset source health, blocking state, counts, safe failures | `summarize_source_health`; `GET /quality/health` | Existing `QualityHealthResponse` | No raw result payload | Reuse existing endpoint | Read-only and available | Fixture-oriented checks and source data remain clearly identified |
| Scenarios | Validated assumptions, interval results, summary, limitations | M06 `run_scenario`; `POST /scenarios`; `GET /scenarios/{scenario_id}` | Existing M06 JSON response | No scenario listing endpoint | Reuse endpoints; add API-bound demo validation | Creation allowed only within configured bounds | Simulations are not forecasts; weather uses a deterministic approximation; humidity does not change values |
| Briefing | Latest deterministic facts and evidence | `GET /briefings/latest` | Existing M06 JSON response | No free-form narrative | Reuse latest read | Read available; generation returns 403 | No free-form or LLM narrative exists; empty state returns 404 |
| Baseline evidence | Latest successful M04 baseline identity and persisted aggregate metrics | M04 baseline run/metric tables | `GET /model-performance/latest` `baseline` | Slice metrics are not in compact C01 response | Added read-only query adapter | Read-only and available | Only persisted metrics are shown; no presentation calculation |
| Model performance | Latest persisted M05 MAE/RMSE/WAPE/bias group | M05 `model_performance_summaries` | `GET /model-performance/latest` `production_metrics` | Peak/ramp error not persisted | Added read-only query adapter | Read-only and available | Peak and ramp error are reported unavailable, not invented |
| Drift/monitoring | Latest persisted feature drift summary group | M05 `model_drift_summaries` | `GET /model-performance/latest` `drift_summaries` | No inferred status threshold | Added read-only query adapter | Read-only and available | Drift is absolute mean difference or explicit no-data output |
| System status | Safe dependency state and latest ingestion, quality, forecast, alert-evaluation, briefing timestamps | M01 readiness plus persisted run tables | `GET /system/status` | No scheduler state exists | Added safe read adapter | Exposes `demo_mode`, not infrastructure details | Does not expose URLs, credentials, hostnames, or claim scheduling |

## Public Demo Contract

`GRIDOPS_DEMO_MODE=true` keeps all read endpoints available. It rejects alert evaluation, alert state changes, and briefing generation with `403`. Scenario execution remains available because it accepts a known forecast identifier and bounded typed assumptions; it does not train a model or alter the source forecast.

Default absolute scenario limits are configurable through `GRIDOPS_DEMO_SCENARIO_*` settings:

- demand growth: 10 percent
- added load: 2,000 MW
- temperature delta: 10 C
- humidity delta: 30 percent

All scenario decimal inputs must be finite in every mode. Demo mode additionally rejects values outside the configured inclusive bounds. Frontend validation is supplementary and must use the same published limits.

## Seeded Demo Strategy

The demo dataset must be labeled fixture-backed demonstration data. M07 should compose the existing fixture ingestion runners, quality services, forecasting persistence/services, alert engine, scenario engine, and briefing generator. It must not introduce parallel fake response files or bypass the persisted contracts above.

The current M02 fixture commands reproducibly seed ingestion inputs but do not alone create a complete M03-M06 dashboard state. M07-C01 therefore does not claim a complete bootstrap command exists. A later M07 chunk may add one lightweight orchestration command only by composing existing services; if that cannot be done without redesigning prior pipelines, the documented fixture/test setup remains the honest demo path.
