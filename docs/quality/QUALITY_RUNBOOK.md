# M03 Quality Runbook

## Purpose

M03 adds a simple persisted quality layer between the M02 silver datasets and future M04 trusted feature work.

The quality runner:

- evaluates one supported dataset at a time
- persists a `quality_run`
- persists one or more `quality_results`
- leaves blocking decisions to the persisted severity and explicit blocking model

The runner does not auto-trigger from ingestion and does not implement orchestration, alerts, or deployment behavior.

## Supported Datasets

- `ieso_hourly_demand`
- `weather_observations`
- `weather_forecasts`
- `raw_snapshots`
- `ingestion_runs`

## Prerequisites

1. PostgreSQL is running.
2. `GRIDOPS_DATABASE_URL` points at the intended database.
3. Alembic is upgraded to head.

Example:

```powershell
$env:GRIDOPS_DATABASE_URL = "postgresql+psycopg://gridops:gridops@127.0.0.1:55432/gridops_test"
uv run alembic upgrade head
```

## Runner Commands

Basic commands:

```powershell
uv run python -m gridops.quality.runner --dataset ieso_hourly_demand
uv run python -m gridops.quality.runner --dataset weather_observations
uv run python -m gridops.quality.runner --dataset weather_forecasts
uv run python -m gridops.quality.runner --dataset raw_snapshots
uv run python -m gridops.quality.runner --dataset ingestion_runs
```

Optional deterministic and scoped flags:

```powershell
uv run python -m gridops.quality.runner --dataset ieso_hourly_demand --checked-window-start-utc 2026-01-15T05:00:00Z --checked-window-end-utc 2026-01-15T08:00:00Z --now-utc 2026-01-15T09:00:00Z
```

Supported flags:

- `--dataset`: required dataset name
- `--checked-window-start-utc`: optional ISO 8601 UTC lower bound
- `--checked-window-end-utc`: optional ISO 8601 UTC upper bound
- `--now-utc`: optional fixed ISO 8601 UTC clock for freshness checks and persisted run timestamps

## Runner Output

The CLI prints a single summary line:

```text
quality_run_id=123 dataset=ieso_hourly_demand status=succeeded persisted_results=9 is_blocked=true blocking_result_count=2
```

Exit behavior:

- exit `0`: run succeeded and the persisted blocking decision is not blocked
- exit `1`: the run failed or the persisted results indicate blocking

## Reading Results

Operational visibility:

- `GET /quality/health`

Persisted tables:

- `quality_runs`
- `quality_results`

Useful inspection examples:

```sql
SELECT id, dataset_name, status, started_at_utc, completed_at_utc
FROM quality_runs
ORDER BY id DESC;

SELECT quality_run_id, dataset_name, check_name, severity, status, is_blocking, safe_detail
FROM quality_results
ORDER BY id DESC;
```

## Blocking Interpretation

Persisted blocking decisions follow the M03 rules:

- `info` does not block
- `warning` does not block by default
- `error` blocks
- `critical` blocks
- explicit `is_blocking=true` blocks
- failed quality runs block

Use the persisted results, not command-line output alone, as the durable source of truth for downstream readiness.

## Empty Dataset Behavior

If a dataset has no rows in scope, the runner persists an honest `dataset_rows_present` failure with `critical` severity instead of crashing.

## Troubleshooting

If the runner exits blocked:

1. Inspect the latest `quality_results` for the dataset.
2. Check `safe_detail`, `observed_value`, and `expected_value`.
3. Confirm the checked window and fixed clock arguments match the intended scope.
4. For IESO DST windows, confirm whether the M02 schema can represent the source-native hour unambiguously.

If the runner itself fails:

1. Inspect the latest `quality_run.safe_error_detail`.
2. Confirm the database is reachable and migrated.
3. Confirm CLI timestamps are timezone-aware UTC.

## Relationship To M04

M04 should consume only trusted dataset windows after reviewing persisted quality state and blocking decisions. The M03 runner provides the durable quality evidence that M04 can reference when creating trusted gold snapshots.

## Current Limitations

- The runner evaluates one dataset per invocation.
- It does not schedule itself or trigger from ingestion.
- Weather continuity and completeness remain fixture-oriented.
- IESO fall-back ambiguity remains limited by the current M02 source-native key design.
