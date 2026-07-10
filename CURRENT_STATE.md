# Current State

## Project

GridOps Intelligence

## Current Phase

M05 active on branch `m05`

## Active Milestone

M05 - Production Forecasting and MLOps

## Milestone Owner

Elena Rossi - Senior ML Platform Engineer

## Project Leader

Samantha

## Repository Status

M01 is complete.

M02 is complete and merged to `main`.

M03 is complete and merged to `main`.

M04 is complete and merged to `main`.

M05 is active on branch `m05`.

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

## Technical State

- Python version: 3.12
- package: `gridops`
- database: PostgreSQL
- local database port: `55432`
- migrations: empty baseline, M02 ingestion storage, M03 quality storage, and M04 forecasting foundation
- API: FastAPI health, readiness, and `GET /quality/health`
- ingestion: fixture mode only through `python -m gridops.ingestion.runner`
- quality: persisted dataset checks through `python -m gridops.quality.runner`
- forecasting evaluation: forecast issue contracts, feature snapshots, baselines, backtest windows, metrics, slice reports, and simple runner previews
- tests: deterministic unit and PostgreSQL integration coverage for M01 through M04

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
- production gradient boosting model
- quantile forecasts or prediction intervals
- MLflow tracking or registry
- scheduled production inference
- production forecast API
- drift monitoring
- alerts
- scenarios
- frontend or dashboards
- authentication
- production deployment

## Verification Evidence

- M02 verification: `docs/verification/M02_VERIFICATION.md`
- M03 verification: `docs/verification/M03_VERIFICATION.md`
- M04 verification: `docs/verification/M04_VERIFICATION.md`

## Immediate Next Action

Begin M05-C01 production forecasting and MLOps contracts after this M05-C00 documentation synchronization.
