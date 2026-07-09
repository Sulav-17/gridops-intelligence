# M04 Handoff

## Milestone Status

M04 - Baselines and Backtesting is complete on branch `m04` and ready for approval.

## Implemented Forecasting Foundation

- UTC forecast issue contract
- deterministic hourly horizon generation
- M04 forecasting evaluation schema
- point-in-time feature snapshot generation
- leakage-safe demand lag, rolling, recent ramp, and calendar features
- weather observation as-of joins
- archived weather forecast issue-time as-of joins
- M03 quality-blocking integration before trusted feature rows are persisted
- same-hour-yesterday baseline
- same-hour-last-week baseline
- seasonal hourly mean baseline
- simple deterministic Ridge baseline
- rolling and expanding backtest window definitions
- final untouched test-period reservation in backtest config
- MAE, RMSE, WAPE, and bias metrics
- slice metrics by lead hour, target hour, day of week, weekend flag, month, and season
- baseline run, prediction, aggregate metric, and slice metric persistence
- simple forecasting runner previews

## Database Tables Added

- `forecast_issues`
- `feature_snapshot_runs`
- `feature_snapshot_rows`
- `baseline_forecast_runs`
- `baseline_forecast_predictions`
- `baseline_metric_results`
- `baseline_slice_metric_results`

## Commands Available

Feature snapshot preview:

```powershell
uv run python -m gridops.forecasting.runner build-features --forecast-issue-time-utc 2026-07-09T15:00:00Z --horizon-hours 24 --dry-run
```

Persist feature snapshots:

```powershell
$env:GRIDOPS_DATABASE_URL = "postgresql+psycopg://gridops:gridops@127.0.0.1:55432/gridops_test"
uv run python -m gridops.forecasting.runner build-features --forecast-issue-time-utc 2026-07-09T15:00:00Z --horizon-hours 24
Remove-Item Env:\GRIDOPS_DATABASE_URL
```

Backtest window preview:

```powershell
uv run python -m gridops.forecasting.runner run-backtest --training-start-utc 2026-07-01T00:00:00Z --start-utc 2026-07-08T00:00:00Z --end-utc 2026-07-10T00:00:00Z --minimum-training-history-hours 24 --dry-run
```

Capability report:

```powershell
uv run python -m gridops.forecasting.runner report --dry-run
```

## Forecast Issue Contract

- Forecast type: `day_ahead_hourly_ontario_demand`
- Default horizon: 24 hourly target intervals
- Forecast issue time: caller-provided aware UTC timestamp
- Default feature version: `m04_c01_foundation`
- Point-in-time rule: `features_must_be_available_at_or_before_forecast_issue_time_utc`

Naive and non-UTC issue datetimes are rejected.

## Feature Snapshot Design

Feature snapshots use the forecast issue time as the knowledge boundary.

Persisted rows retain:

- forecast issue time
- target interval start and end UTC
- lead hour
- feature version
- quality status
- practical source row references
- structured feature payload JSON in `lineage_metadata`

Feature groups:

- demand lags: 1h, 2h, 24h, 48h, 168h
- rolling demand mean, min, max, standard deviation
- recent ramp
- UTC calendar features
- latest weather observations as of issue time
- archived weather forecasts selected by latest issue time at or before issue time

## As-Of Join Behavior

- Weather observations require `observed_at_utc <= forecast_issue_time_utc`.
- Archived weather forecasts require `issue_time_utc <= forecast_issue_time_utc`.
- Archived forecast selection is latest issue time per `(forecast_location, variable_name, valid_time_utc)`, with persisted row id as deterministic tie-breaker.
- Target actual demand is never used as an input feature.

## Baselines Implemented

- `same_hour_yesterday`
- `same_hour_last_week`
- `seasonal_hourly_mean`
- `ridge`

Ridge is a simple scikit-learn `StandardScaler` plus `Ridge(alpha=1.0)` baseline. It is not a production model and is not registered.

## Backtesting Design

M04 supports deterministic rolling or expanding windows with:

- training start
- evaluation start and end
- forecast horizon
- step size
- minimum training history
- optional rolling training-window length
- optional final untouched test-period reservation

No random split is used.

## Metrics Implemented

- MAE
- RMSE
- WAPE
- bias

Skipped/null predictions are ignored. WAPE is omitted when the actual-demand denominator is zero.

## Slice Reporting

Slice metrics are implemented for:

- lead hour
- target hour
- day of week
- weekend flag
- month
- season

## Lineage Behavior

M04 preserves lineage through:

- feature version
- forecast issue time
- target interval
- quality status
- source row references where practical
- structured JSON feature payloads
- baseline run metadata
- prediction lineage metadata
- metric and slice metric persistence

## Verification Summary

- `uv run ruff format --check .`: passed
- `uv run ruff check .`: passed
- `uv run mypy src tests`: passed
- `uv run pytest -q`: `150 passed, 2 warnings`
- `uv run alembic current`: `c1f3a9d7e4b2 (head)`
- clean migration verification passed after the documented `alembic stamp base` workaround

Exact results are recorded in `docs/verification/M04_VERIFICATION.md`.

## Known Limitations

- Fixture-backed/local data only.
- Feature payloads are stored as JSON rather than dedicated typed feature columns.
- Ridge is a simple baseline only.
- Runner is a deterministic helper, not an orchestrator.
- No production forecast model exists.
- No prediction intervals exist.
- No MLflow registry exists.
- No scheduled inference exists.
- No forecast API exists.
- No drift monitoring, alerts, scenarios, dashboard, or deployment exists.
- No production performance claims are made.

## Risks For M05

- M05 should decide whether JSON feature payloads are sufficient for production training or whether a typed feature table is needed.
- M05 should not treat M04 baseline outputs as production forecasts.
- M05 must preserve the point-in-time and M03 quality-blocking rules.
- M05 model selection should compare production candidates against the persisted M04 baselines.
- M05 should introduce MLflow and production model registry only after explicit model-selection gates are defined.
- M05 should handle prediction intervals and scheduled inference as new production-scope work.

## Exact Recommended Next Step

Begin M05 by defining production forecasting and MLOps contracts: model-selection gates, MLflow experiment/registry behavior, production candidate training scope, quantile output schema, scheduled inference boundaries, and forecast API contracts.
