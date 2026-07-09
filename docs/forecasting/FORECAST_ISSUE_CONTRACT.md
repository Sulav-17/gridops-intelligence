# Forecast Issue Contract

## Status

Draft M04-C01 contract foundation. This document describes implemented contract and schema assumptions only; feature generation, baselines, backtesting, and production forecasting are not implemented in this chunk.

## Implemented Contract

- Forecast type: `day_ahead_hourly_ontario_demand`
- Default horizon: 24 hourly target intervals
- Forecast issue time: caller-provided `forecast_issue_time_utc`
- Feature version: `m04_c01_foundation`
- Point-in-time rule: `features_must_be_available_at_or_before_forecast_issue_time_utc`

All contract datetimes must be timezone-aware UTC. Naive datetimes and non-UTC aware datetimes are rejected.

## Horizon Generation

Given a forecast issue time, M04-C01 generates the next N complete hourly UTC intervals strictly after the issue time.

For an issue at `2026-07-09T15:00:00Z`, the first target interval is `2026-07-09T16:00:00Z` to `2026-07-09T17:00:00Z`, with `lead_hour = 1`.

For an issue inside an hour, such as `2026-07-09T15:30:00Z`, the first target interval is still the next complete hour: `2026-07-09T16:00:00Z` to `2026-07-09T17:00:00Z`.

## Time And Local Interpretation

Canonical operational timestamps remain UTC. Ontario local interpretation remains `America/Toronto` under the M01 time rules. M04-C01 does not reinterpret IESO hour-ending fields or create local-time feature logic.

## Quality And Lineage Assumptions

The M04-C01 schema includes fields for quality status, quality blocking behavior, feature version, source row references, and lineage metadata. Later M04 chunks must fill these fields when building point-in-time feature snapshots and baseline evaluations.

M04-C01 does not silently trust source data. It only creates the storage foundation needed for later chunks to apply M03 blocking decisions.

## Deferred Work

- feature snapshot generation
- demand lag and rolling features
- weather observation and archived forecast as-of joins
- baseline model implementations
- backtesting windows
- metric computation
- runner commands
- production forecast serving
