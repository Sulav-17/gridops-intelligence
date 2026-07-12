# Current State

## Project

GridOps Intelligence

## Current Phase

M07 active on branch `m07`

## Active Milestone

M07 - Dashboard, Deployment, and Release

## Milestone Owner

Olivia Grant - Senior Product and Deployment Engineer

## Project Leader

Samantha

## Repository Status

M01 is complete.

M02 is complete and merged to `main`.

M03 is complete and merged to `main`.

M04 is complete and merged to `main`.

M05 is complete.

M06 is complete on branch `m06`.

M07-C01 backend integration contracts, M07-C02 frontend foundation, and M07-C03 alert/scenario/briefing decision-support screens are implemented on branch `m07`; M07 is not complete.

Implemented storage includes:

- `ingestion_runs`
- `raw_snapshots`
- `ieso_hourly_demand`
- `weather_observations`
- `weather_forecasts`
- `quality_runs`
- `quality_results`
- `forecast_issues`
- `feature_snapshot_runs`
- `feature_snapshot_rows`
- `baseline_forecast_runs`
- `baseline_forecast_predictions`
- `baseline_metric_results`
- `baseline_slice_metric_results`
- `model_training_runs`
- `model_artifacts`
- `model_selection_results`
- `production_forecast_runs`
- `production_forecast_predictions`
- `forecast_peak_outputs`
- `forecast_ramp_outputs`
- `model_performance_summaries`
- `model_drift_summaries`
- `alert_evaluation_runs`
- `alerts`
- `alert_evidence`
- `alert_lifecycle_history`
- `scenario_runs`
- `scenario_assumptions`
- `scenario_result_rows`
- `briefing_runs`
- `briefing_facts`

## Technical State

- Python version: 3.12
- package: `gridops`
- database: PostgreSQL
- local database port: `55432`
- migrations: empty baseline, M02 ingestion storage, M03 quality storage, M04 forecasting foundation, M05 production forecasting schema, M06 alert foundation, and M06 scenario/briefing schema
- API: FastAPI health, readiness, quality, alert, scenario, briefing, dashboard overview, production forecast read, model-performance read, and safe system-status endpoints
- M07 demo mode: typed configuration disables public alert evaluation, alert lifecycle mutation, and briefing generation while allowing only bounded scenario execution
- M07 frontend: Next.js App Router dashboard shell, typed API client, explicit fixture-backed demo fallback, responsive overview, forecast, alerts and immutable evidence/lifecycle detail, bounded scenario simulations, deterministic briefing facts, data quality, model-performance, and safe system-status screens
- ingestion: fixture mode only through `python -m gridops.ingestion.runner`
- quality: persisted dataset checks through `python -m gridops.quality.runner`
- forecasting evaluation: forecast issue contracts, feature snapshots, baselines, backtest windows, metrics, slice reports, and simple runner previews
- M05 artifact foundation: local artifact save/load, SHA-256 hashing, and model artifact metadata persistence
- M05 selection foundation: deterministic model-selection gate and persisted selection results
- M05 candidate training: deterministic sklearn candidate training from M04 feature snapshots, persisted training runs, artifact persistence, metric calculation, and model-selection results
- M05 forecast generation: selected-artifact forecast output persistence with P50 predictions, nullable P10/P90, peak output, ramp outputs, and lineage
- M05 monitoring foundation: persisted forecast-vs-actual performance summaries and simple feature drift summaries
- M05 runner: deterministic production runner command boundaries for candidate training, forecast generation, and monitoring summaries
- M06 alert foundation: deterministic alert contracts, high-demand/ramp/previous-forecast-deviation/source-health/combined-context rules, duplicate-active alert prevention, immutable alert evidence, and lifecycle history
- M06 scenario foundation: deterministic demand-growth, approximate weather-adjustment, and combined weather/load scenarios with persisted assumptions, limitations, and result rows
- M06 briefing foundation: deterministic structured briefing facts with evidence references and backend API output
- M06 decision runner: standard-library commands for alert evaluation, scenario runs, and briefing generation
- tests: deterministic unit and PostgreSQL integration coverage for M01 through M06

## Implemented M04 Capabilities

- forecast issue contract with aware UTC issue time validation
- deterministic hourly horizon generation
- M04 forecasting schema foundation
- point-in-time feature snapshot generation
- leakage-safe demand lag, rolling, recent ramp, and calendar features
- as-of weather observation joins
- archived weather forecast issue-time as-of joins
- M03 quality-blocking integration for feature snapshot generation
- same-hour-yesterday baseline
- same-hour-last-week baseline
- seasonal hourly mean baseline
- simple deterministic Ridge baseline
- rolling and expanding backtest window definitions
- final untouched test-period reservation in backtest config
- MAE, RMSE, WAPE, and bias calculations
- slice metrics by lead hour, target hour, day of week, weekend flag, month, and season
- persisted baseline run, prediction, aggregate metric, and slice metric rows
- simple forecasting runner through `python -m gridops.forecasting.runner`
- forecasting runbooks, baseline report, verification report, and handoff artifacts

## Not Implemented Yet

- live source fetching
- IESO API clients
- weather provider API clients
- scheduled ingestion
- Prefect
- dbt
- LightGBM or XGBoost production candidate
- true quantile forecasts or prediction intervals
- MLflow tracking or registry
- scheduled production inference
- authentication
- production deployment

## Verification Evidence

- M02 verification: `docs/verification/M02_VERIFICATION.md`
- M03 verification: `docs/verification/M03_VERIFICATION.md`
- M04 verification: `docs/verification/M04_VERIFICATION.md`
- M05 verification: `docs/verification/M05_VERIFICATION.md`
- M06 verification: `docs/verification/M06_VERIFICATION.md`

## Immediate Next Action

Continue M07 with C04 deployment, release artifacts, and final verification. C03 validation covers client-side bounds, finite values, safe server errors, duplicate-submit prevention, fixture labeling, and the absence of public mutation, ingestion, training, inference, or model-promotion controls. The previous backend pytest invocation timed out at 99%; final C03 verification must replace that result with a completed suite outcome.
