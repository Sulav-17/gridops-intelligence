# M03 Quality Contracts

## Scope

M03 quality contracts cover the existing M02 datasets only:

- `ieso_hourly_demand`
- `weather_observations`
- `weather_forecasts`
- `raw_snapshots`
- `ingestion_runs`

The contracts define the persisted quality vocabulary, dataset field expectations, conservative thresholds, and blocking semantics used by the M03 checks and runner.

## Severity Model

- `info`: non-blocking informational result
- `warning`: visible but non-blocking by default
- `error`: blocks the affected dataset or checked window
- `critical`: blocks the dataset or source scope

An explicit persisted `is_blocking=true` result blocks regardless of severity.

## Result Status Model

- `passed`
- `failed`
- `skipped`
- `error`

## Check Categories

- `schema`
- `completeness`
- `continuity`
- `uniqueness`
- `range`
- `freshness`
- `timestamp`
- `dst`
- `source_metadata`

## Dataset Contracts

### `ieso_hourly_demand`

Required fields:

- `id`
- `source_service_date`
- `source_hour_ending`
- `interval_start_utc`
- `interval_end_utc`
- `demand_mw`
- `source_snapshot_id`
- `ingestion_run_id`
- `row_hash_sha256`
- `is_current`

Source-native fields:

- `source_service_date`
- `source_hour_ending`

Checks implemented:

- required-column schema check
- required-value nullability check
- current source-key uniqueness check
- conservative `demand_mw` range check
- UTC timestamp ordering and one-hour duration check
- hourly UTC continuity check
- source-hour completeness check
- fixed-clock freshness check
- DST alignment check using M01 time utilities

Thresholds and assumptions:

- `0 <= demand_mw <= 60000`
- freshness tolerance defaults to 30 hours
- IESO hour-ending behavior follows the M01 Toronto and UTC conversion contract

### `weather_observations`

Required fields:

- `id`
- `source_name`
- `source_station_id`
- `source_native_timestamp`
- `observed_at_utc`
- `source_snapshot_id`
- `ingestion_run_id`
- `row_hash_sha256`
- `is_current`

Checks implemented:

- required-column schema check
- required-value nullability check
- current source-key uniqueness check
- conservative temperature, humidity, wind, and precipitation range checks
- UTC timestamp check
- fixture-supported hourly continuity check
- fixed-clock freshness check

Thresholds and assumptions:

- `-80 <= temperature_c <= 60`
- `0 <= relative_humidity_percent <= 100` when present
- `wind_speed_kph >= 0` when present
- `precipitation_mm >= 0` when present
- freshness tolerance defaults to 6 hours
- continuity is limited to hourly fixture-style assumptions

### `weather_forecasts`

Required fields:

- `id`
- `source_name`
- `forecast_location`
- `source_native_issue_time`
- `source_native_valid_time`
- `issue_time_utc`
- `valid_time_utc`
- `variable_name`
- `variable_value`
- `source_snapshot_id`
- `ingestion_run_id`
- `row_hash_sha256`
- `is_current`

Checks implemented:

- required-column schema check
- required-value nullability check
- current forecast-key uniqueness check
- conservative provider-neutral `variable_value` range check
- UTC issue/valid timestamp and lead-time check
- fixture-supported valid-time completeness check
- fixed-clock freshness check

Thresholds and assumptions:

- `-1000 <= variable_value <= 1000`
- `valid_time_utc` must be after `issue_time_utc`
- `lead_time_hours` must match the whole-hour issue-to-valid difference when present
- freshness tolerance defaults to 24 hours
- completeness is limited to fixture-supported current issue groups

### `raw_snapshots`

Required fields:

- `id`
- `source_name`
- `source_type`
- `retrieved_at_utc`
- `content_hash_sha256`
- `content_type`
- `parser_version`
- `storage_path`
- `byte_size`
- `ingestion_run_id`

Checks implemented:

- required source metadata check

Thresholds and assumptions:

- `byte_size >= 0`
- `retrieved_at_utc` must be timezone-aware UTC

### `ingestion_runs`

Required fields:

- `id`
- `source_name`
- `source_type`
- `mode`
- `parser_version`
- `status`
- `started_at_utc`
- `records_seen`
- `records_loaded`

Checks implemented:

- ingestion lifecycle and metadata check

Thresholds and assumptions:

- valid statuses are `running`, `succeeded`, and `failed`
- terminal runs require `finished_at_utc`
- `records_seen >= 0`
- `records_loaded >= 0`
- stored failure detail must remain safe and bounded

## Blocking Behavior

Persisted blocking decisions use the latest applicable quality run:

- `info` does not block
- `warning` does not block by default
- `error` blocks
- `critical` blocks
- explicit `is_blocking=true` blocks
- a failed quality run blocks and is treated as critical at decision time

The quality runner exits with code `0` only when the persisted run succeeds and the resulting blocking decision is not blocked.

## Freshness Clocks

Freshness checks accept a caller-provided fixed UTC clock. The runner exposes this through `--now-utc`, which is also used for persisted run timestamps when supplied so deterministic tests and manual verification can reproduce exact outcomes.

## DST Assumptions

- M03 does not weaken M01 Toronto and UTC time behavior.
- IESO DST validation supports spring-forward records that the current M02 schema can represent.
- The current M02 IESO source-native key cannot fully distinguish the repeated fall-back operating hour without additional source-native detail.
- Fall-back ambiguity is reported honestly as skipped or limited behavior rather than being faked.

## Known Limitations

- Contracts cover only the existing M02 datasets.
- Weather continuity and completeness remain fixture-oriented, not provider-contract-specific.
- Forecast range thresholds are intentionally broad and not official provider operating limits.
- Quality tables do not store raw payloads, secrets, or future-domain entities.
