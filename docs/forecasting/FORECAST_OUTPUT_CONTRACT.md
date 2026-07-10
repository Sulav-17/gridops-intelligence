# Forecast Output Contract

## Status

M05 implements database and typed-contract foundations for production forecast outputs. It does not expose a production forecast API or scheduler.

## Forecast Run Fields

`production_forecast_runs` records:

- model artifact id
- feature snapshot run id
- model name, type, and version
- feature version
- forecast issue time UTC
- status
- quality status when available
- lineage metadata
- started, completed, and created UTC timestamps
- safe error detail

## Prediction Fields

`production_forecast_predictions` records:

- production forecast run id
- feature snapshot row id
- forecast issue time UTC
- target interval start and end UTC
- lead hour
- P50 demand MW or point forecast demand MW
- nullable P10 and P90 demand MW
- prediction type
- lineage metadata
- created timestamp UTC

## Quantile Fields

P10 and P90 fields exist but remain nullable. M05-C04 persists P50-only predictions and does not fake prediction intervals.

## Peak Output Fields

`forecast_peak_outputs` records:

- production forecast run id
- peak target interval start and end UTC
- peak demand MW
- peak lead hour
- lineage metadata
- created timestamp UTC

## Ramp Output Fields

`forecast_ramp_outputs` records:

- production forecast run id
- target interval start UTC
- previous target interval start UTC
- forecast ramp MW
- absolute ramp MW
- lineage metadata
- created timestamp UTC

## Lineage Fields

Forecast generation preserves:

- model artifact id
- model training run id when available
- feature snapshot run id
- feature snapshot row id for predictions
- feature version
- forecast issue time UTC

## Quality Fields

Forecast generation reuses or builds M04 feature snapshots. Blocked or unusable feature snapshots produce a blocked forecast run and no predictions.

## Monitoring Fields

M05 monitoring summaries persist:

- forecast-vs-actual MAE, RMSE, WAPE, and bias where actuals exist
- simple feature drift absolute mean differences
- model/artifact reference
- window bounds
- row counts or no-data summary JSON
- lineage metadata

## Non-Operational Disclaimer

GridOps Intelligence forecast outputs are decision-support artifacts. They do not dispatch resources, issue emergency declarations, replace IESO forecasts, or provide reliability certification.

## Known Limitations

- No production forecast API exists.
- No real scheduler exists.
- No prediction intervals are implemented.
- No alerts, scenarios, briefing generation, dashboard, authentication, or deployment is implemented.
- No production performance claims are made.
