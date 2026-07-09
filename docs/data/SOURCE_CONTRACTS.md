# Source Contracts

## Implemented In M02

M02 supports deterministic fixture ingestion for three sources:

- `ieso-demand`: fixture-backed IESO hourly demand.
- `weather-observations`: fixture-backed weather observations.
- `weather-forecasts`: fixture-backed archived weather forecasts.

All automated tests use local fixtures only. No live source fetching or provider API client is implemented.

## Shared Bronze Contract

Raw snapshots preserve:

- source name and source type
- fixture retrieval identifier
- retrieval timestamp in UTC
- optional publication timestamp
- content type
- SHA-256 content hash
- parser version
- storage path
- byte size
- ingestion run reference

Identical raw payloads for the same source reuse the existing raw snapshot metadata row.

## Shared Silver Contract

Silver rows preserve:

- source-native fields required for traceability
- normalized UTC timestamps
- raw snapshot reference
- ingestion run reference
- row-level SHA-256 hash
- `is_current`
- `superseded_at_utc`

Changed records for the same natural key create a new version and mark the previous current row superseded.

## IESO Demand Fixture

Fixture format: CSV with columns:

```text
service_date,hour_ending,demand_mw
```

Assumptions:

- `service_date` is an Ontario service date formatted `YYYY-MM-DD`.
- `hour_ending` uses IESO hour-ending values `1` through `24`.
- `hour_ending` labels the local Toronto operating-hour endpoint and is converted with `gridops.time_utils.ieso_hour_ending_to_utc`.
- `demand_mw` is parsed as a decimal megawatt value.

Preserved source-native fields:

- service date string
- hour-ending integer

Known uncertainty:

- DST transition-day source behavior is not inferred in M02. The M01 time utilities reject ambiguous or nonexistent endpoints.

## Weather Observations Fixture

Fixture format: CSV with columns:

```text
station_id,observed_at,temperature_c,relative_humidity_percent,wind_speed_kph,precipitation_mm
```

Assumptions:

- `observed_at` is an ISO timestamp with timezone information.
- Missing weather variable values are allowed where the fixture leaves a field blank.
- Provider selection remains deferred.

Preserved source-native fields:

- station identifier
- original observation timestamp string

## Archived Weather Forecast Fixture

Fixture format: CSV with columns:

```text
location,issue_time,valid_time,variable_name,variable_value,variable_unit
```

Assumptions:

- `issue_time` and `valid_time` are ISO timestamps with timezone information.
- `lead_time_hours` is derived when valid time minus issue time is an exact whole number of hours.
- Provider selection remains deferred.

Preserved source-native fields:

- forecast location
- issue timestamp string
- valid timestamp string
- forecast variable name and unit

## Deferred

- Live IESO fetching.
- Live or archived weather provider API integration.
- Formal data-quality severity framework.
- Source-health scoring.
- Gold feature tables.
- Forecasting and backtesting.
