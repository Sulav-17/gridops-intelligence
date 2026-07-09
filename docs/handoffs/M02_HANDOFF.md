# M02 Handoff

## Milestone Status

M02 - Data Ingestion Foundation is complete.

## Implemented Capabilities

- ingestion run tracking
- raw snapshot metadata persistence
- local raw payload storage by source and SHA-256 hash
- source registry contract
- fixture-backed IESO hourly demand parser and loader
- fixture-backed weather observation parser and loader
- fixture-backed archived weather forecast parser and loader
- idempotent silver loading
- simple changed-record revision evidence
- simple fixture ingestion runner
- deterministic tests for storage, parsers, loaders, runner, and migrations

## Database Tables Added

- `ingestion_runs`
- `raw_snapshots`
- `ieso_hourly_demand`
- `weather_observations`
- `weather_forecasts`

## Commands Available

```powershell
uv run python -m gridops.ingestion.runner --source ieso-demand --mode fixture --path tests/fixtures/ingestion/ieso/hourly_demand_sample.csv
uv run python -m gridops.ingestion.runner --source weather-observations --mode fixture --path tests/fixtures/ingestion/weather/observations_sample.csv
uv run python -m gridops.ingestion.runner --source weather-forecasts --mode fixture --path tests/fixtures/ingestion/weather/forecasts_sample.csv
```

Use `GRIDOPS_DATABASE_URL` to target the intended PostgreSQL database.

## Source Assumptions

- IESO fixture dates are Ontario service dates.
- IESO hour-ending values are labels for local Toronto operating-hour endpoints.
- Weather observation timestamps are timezone-aware ISO timestamps.
- Archived weather forecast issue and valid timestamps are timezone-aware ISO timestamps.
- Weather provider choice is intentionally deferred.

## Idempotency Behavior

- Identical raw payloads for the same source reuse the existing raw snapshot record.
- Repeated silver loads skip unchanged current rows.
- Changed source values create new row-hash versions.

## Revision Behavior

M02 uses simple current-state revision evidence:

- `row_hash_sha256`
- `is_current`
- `superseded_at_utc`

This is not a full bitemporal model.

## Known Limitations

- Fixture ingestion only.
- No live fetching.
- No scheduling or orchestration.
- No formal data-quality severity framework.
- No source-health tables.
- No gold feature tables.
- No forecasting or backtesting.
- No alerts, scenarios, dashboards, or deployment.

## M03 Readiness

M03 can build formal data-quality checks on top of:

- persisted raw evidence
- source metadata
- ingestion run statuses
- normalized UTC timestamps
- preserved source-native fields
- row hashes and current/superseded revision state

## Recommended Next Step

Start M03 by defining data-quality contracts and checks for the existing M02 tables, beginning with schema, uniqueness, completeness, timestamp continuity, freshness, and DST-specific IESO checks.
