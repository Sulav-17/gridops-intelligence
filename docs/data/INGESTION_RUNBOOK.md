# Ingestion Runbook

## Implemented Commands

M02 provides a simple fixture runner:

```powershell
uv run python -m gridops.ingestion.runner --source ieso-demand --mode fixture --path tests/fixtures/ingestion/ieso/hourly_demand_sample.csv
uv run python -m gridops.ingestion.runner --source weather-observations --mode fixture --path tests/fixtures/ingestion/weather/observations_sample.csv
uv run python -m gridops.ingestion.runner --source weather-forecasts --mode fixture --path tests/fixtures/ingestion/weather/forecasts_sample.csv
```

Optional raw snapshot root:

```powershell
uv run python -m gridops.ingestion.runner --source ieso-demand --mode fixture --path tests/fixtures/ingestion/ieso/hourly_demand_sample.csv --raw-root data/raw
```

The runner uses `GRIDOPS_DATABASE_URL`. For local test database runs:

```powershell
$env:GRIDOPS_DATABASE_URL = "postgresql+psycopg://gridops:gridops@127.0.0.1:55432/gridops_test"
```

## Migrations

Apply migrations:

```powershell
uv run alembic upgrade head
```

Check current migration:

```powershell
uv run alembic current
```

## Raw Snapshots

Raw payload files are stored under the configured raw root by source and content hash. The default root is `data/raw`, which is ignored by Git.

Raw snapshot database rows record source metadata, retrieval metadata, parser version, content type, SHA-256 hash, byte size, storage path, and ingestion run ID.

## Idempotency

Raw snapshots dedupe identical payloads per source by SHA-256 hash.

Silver loaders skip unchanged current records. For changed values on the same natural key, loaders mark the previous row non-current and insert a new current row with a new row hash.

## Failure Recording

The runner creates an ingestion run before parsing or loading. If payload read, parsing, snapshot persistence, or loading fails, it records a failed ingestion run with bounded redacted error detail.

Partial silver writes are rolled back when failures occur before success commit.

## Verification

Run:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest -q
```

## Optional Live Smoke Checks

No live smoke checks are implemented in M02. Live source behavior and provider selection are deferred.

## Current Limitations

- Fixture mode only.
- No scheduling or orchestration.
- No live source clients.
- No formal M03 data-quality framework.
- Weather provider contracts are intentionally provider-neutral fixture assumptions.
- DST transition-day IESO source behavior remains explicit and conservative through M01 time utilities.
