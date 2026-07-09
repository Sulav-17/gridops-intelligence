# Feature Snapshot Contract

## Status

Draft M04-C02 feature snapshot contract. This document describes implemented point-in-time feature behavior only. Baselines, backtesting, metrics, runners, and production forecasts remain deferred.

## Point-In-Time Rules

Feature snapshot generation uses `forecast_issue_time_utc` as the knowledge boundary.

- Demand features use only current demand rows with `interval_end_utc <= forecast_issue_time_utc`.
- Weather observation features use only current observations with `observed_at_utc <= forecast_issue_time_utc`.
- Archived weather forecast features use only current forecast rows with `issue_time_utc <= forecast_issue_time_utc`.
- Archived forecast selection is by latest allowed `issue_time_utc` per `forecast_location`, `variable_name`, and target `valid_time_utc`, with persisted row id as a deterministic tie-breaker.
- Target actual demand is not used as a feature.

## Implemented Feature Groups

Demand features:

- `lag_1h_mw`
- `lag_2h_mw`
- `lag_24h_mw`
- `lag_48h_mw`
- `lag_168h_mw`
- `rolling_mean_mw`
- `rolling_min_mw`
- `rolling_max_mw`
- `rolling_std_mw`
- `recent_ramp_mw`

Missing history is represented as `null`.

Calendar features:

- UTC target hour
- UTC day of week
- month
- season
- weekend flag
- dependency-free cyclic hour sine and cosine

Holiday handling is deferred.

## Persistence

C02 uses the M04-C01 schema. `feature_snapshot_runs` stores run status and quality status. `feature_snapshot_rows` stores forecast issue time, target interval, lead hour, feature version, quality status, practical source row references, and a structured JSON feature payload in `lineage_metadata`.

## Quality Blocking

Before persisting trusted rows, snapshot generation checks M03 blocking decisions for:

- `ieso_hourly_demand`
- `weather_observations`
- `weather_forecasts`

If any required dataset is blocked, the snapshot run is persisted with `status = blocked`, `quality_status = blocked`, and no trusted feature rows are created.

## Deferred Work

- dedicated typed feature columns or indexed feature store design
- holiday features
- richer weather feature aggregation
- baseline models
- backtesting and metrics
- runner commands
