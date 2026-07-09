# Backtesting Runbook

## Purpose

M04 provides a deterministic forecasting evaluation foundation. It supports point-in-time feature snapshots, baseline models, time-based backtest windows, aggregate metrics, slice metrics, and persistence into M04 evaluation tables.

This runbook does not describe production forecasting. M05 owns production model selection, serving, scheduled inference, MLflow registry, monitoring, and forecast APIs.

## Prerequisites

1. PostgreSQL is running.
2. `GRIDOPS_DATABASE_URL` points at the intended database.
3. Alembic is upgraded to head.
4. Fixture ingestion and M03 quality checks have been run if using persisted source data.

Example:

```powershell
$env:GRIDOPS_DATABASE_URL = "postgresql+psycopg://gridops:gridops@127.0.0.1:55432/gridops_test"
uv run alembic upgrade head
```

## Build Feature Snapshot Preview

Dry-run feature snapshot generation:

```powershell
uv run python -m gridops.forecasting.runner build-features --forecast-issue-time-utc 2026-07-09T15:00:00Z --horizon-hours 24 --dry-run
```

The command emits deterministic JSON and does not write rows.

Persist feature snapshots:

```powershell
uv run python -m gridops.forecasting.runner build-features --forecast-issue-time-utc 2026-07-09T15:00:00Z --horizon-hours 24
```

Persisted rows use:

- `forecast_issues`
- `feature_snapshot_runs`
- `feature_snapshot_rows`

If M03 quality state blocks a required dataset, snapshot generation persists a blocked run and does not create trusted feature rows.

## Preview Backtest Windows

Dry-run backtest windows:

```powershell
uv run python -m gridops.forecasting.runner run-backtest --training-start-utc 2026-07-01T00:00:00Z --start-utc 2026-07-08T00:00:00Z --end-utc 2026-07-10T00:00:00Z --minimum-training-history-hours 24 --dry-run
```

Useful flags:

- `--horizon-hours`
- `--step-hours`
- `--minimum-training-history-hours`
- `--final-test-period-start-utc`
- `--final-test-period-end-utc`
- `--window-strategy expanding`
- `--window-strategy rolling --rolling-training-window-hours 168`
- `--models same_hour_yesterday same_hour_last_week seasonal_hourly_mean ridge`
- `--output-path`

Backtest windows are ordered and deterministic. No random split is used.

## Reports

Summarize implemented M04 evaluation capabilities:

```powershell
uv run python -m gridops.forecasting.runner report --dry-run
```

Summarize a prior JSON runner output:

```powershell
uv run python -m gridops.forecasting.runner report --input-path .\backtest-preview.json
```

## Metrics

Implemented metrics:

- MAE
- RMSE
- WAPE
- bias

Skipped predictions and rows with null prediction or actual values are ignored. WAPE is omitted when the actual-demand denominator is zero.

## Slice Metrics

Implemented slices:

- lead hour
- target hour
- day of week
- weekend flag
- month
- season

Slice metrics can be persisted to `baseline_slice_metric_results`.

## Final Test Period Protection

Use `--final-test-period-start-utc` and `--final-test-period-end-utc` to reserve an untouched final period. Generated backtest windows stop before the reserved final test-period start.

## Current Limitations

- M04 uses fixture-backed/local data foundations.
- Feature values are stored as JSON in `feature_snapshot_rows.lineage_metadata`.
- The runner is intentionally simple and is not an orchestrator.
- Ridge is a simple baseline, not a production model.
- No MLflow registry, production forecast API, scheduled inference, prediction intervals, alerts, scenarios, dashboard, or deployment exists.
