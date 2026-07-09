# Baseline Report

## Status

M04 baseline evaluation foundation is implemented on branch `m04`, pending approval and merge.

This report documents implemented evaluation capabilities only. It does not make production forecasting or operational performance claims.

## Baselines Implemented

### `same_hour_yesterday`

Uses the current demand row from 24 hours before the target interval start.

Rules:

- uses only rows with `interval_end_utc <= forecast_issue_time_utc`
- skips predictions when the lag row is missing
- does not use target actual demand as an input feature

### `same_hour_last_week`

Uses the current demand row from 168 hours before the target interval start.

Rules:

- uses only rows with `interval_end_utc <= forecast_issue_time_utc`
- skips predictions when the lag row is missing
- does not use target actual demand as an input feature

### `seasonal_hourly_mean`

Uses the mean historical demand for rows inside the training window that match the target UTC hour.

Rules:

- uses only rows inside the configured training window
- uses only rows available at or before the forecast issue time
- skips predictions when no matching training history exists

### `ridge`

Uses a deterministic scikit-learn pipeline:

- `StandardScaler`
- `Ridge(alpha=1.0)`

Rules:

- training rows are selected by time-based training-window bounds
- no random split is used
- no hyperparameter tuning is implemented
- missing feature payloads produce skipped predictions
- no model artifact registry is created

## Backtesting Design

M04 implements deterministic rolling or expanding backtest window definitions with:

- training start
- evaluation start and end
- forecast horizon
- step size
- minimum training history
- optional rolling training-window length
- optional final untouched test-period reservation

## Metrics Implemented

- MAE
- RMSE
- WAPE
- bias

Skipped predictions and null prediction/actual rows are ignored safely. WAPE is omitted when the actual-demand denominator is zero.

## Slice Reports

Implemented slice dimensions:

- lead hour
- target hour
- day of week
- weekend flag
- month
- season

Slice metrics are represented as structured Python objects and can be persisted to `baseline_slice_metric_results`.

## Persistence

M04 uses the C01 baseline evaluation tables:

- `baseline_forecast_runs`
- `baseline_forecast_predictions`
- `baseline_metric_results`
- `baseline_slice_metric_results`

Stored fields include baseline name, feature version, training/evaluation windows where available, forecast issue time, target intervals, lead hour, prediction value, actual value where available, metric name/value, slice dimension/value, and lineage metadata.

## Limitations

- Baselines are evaluation references, not production forecasts.
- Ridge is simple and deterministic, without tuning or registry support.
- M04 does not claim a production accuracy level.
- M04 does not implement LightGBM, XGBoost, quantile forecasting, prediction intervals, MLflow, scheduled inference, forecast APIs, alerts, scenarios, dashboard, or deployment.
