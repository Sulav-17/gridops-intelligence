# Baseline Report

## Status

Draft M04-C03 baseline evaluation note. This is not a final M04 verification report and does not make production performance claims.

## Implemented Baselines

- `same_hour_yesterday`: uses the current demand row from 24 hours before the target interval.
- `same_hour_last_week`: uses the current demand row from 168 hours before the target interval.
- `seasonal_hourly_mean`: uses only training-window demand rows matching the target UTC hour.
- `ridge`: uses a deterministic `StandardScaler` plus `Ridge(alpha=1.0)` pipeline over point-in-time feature payloads.

Missing history or missing feature values produce skipped/null predictions rather than invented values.

## Backtesting Foundation

C03 provides deterministic rolling or expanding backtest window construction with:

- training start
- evaluation start and end
- forecast horizon
- step size
- minimum training history
- optional final untouched test-period reservation

No random split is used.

## Metrics

Implemented aggregate metrics:

- MAE
- RMSE
- WAPE, omitted when the actual-demand denominator is zero
- bias

Skipped predictions and null prediction/actual pairs are ignored safely.

## Slice Reports

Implemented slice dimensions:

- lead hour
- target hour
- day of week
- weekend flag
- month
- season

Results can be persisted to the existing M04 baseline metric and slice metric tables.

## Limitations

- Ridge is a transparent baseline only, not a production model.
- No hyperparameter tuning is implemented.
- No MLflow registry, scheduled inference, forecast API, alerts, scenarios, dashboard, or deployment work is included.
- Final M04 verification and handoff remain deferred.
