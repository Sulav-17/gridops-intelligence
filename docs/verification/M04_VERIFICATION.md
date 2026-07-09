# M04 Verification

## Status

M04 status: PASS

## Branch And Commit Context

- Branch: `m04`
- Verified against the current `m04` working tree on July 9, 2026
- M04 is complete on branch `m04`, pending approval and merge

## Environment

- OS shell: PowerShell
- Python: project configured for Python 3.12
- Database: local PostgreSQL `gridops_test` on `127.0.0.1:55432`
- Network use: dependency resolution for `scikit-learn` during M04-C03 was approved and recorded in the C03 work; final C04 verification did not require network access

## UV Cache Workaround

Verification used workspace-local paths to avoid the known Windows uv/cache permission issue:

- `UV_CACHE_DIR=C:\Users\Sulav\Desktop\projects\gridops-intelligence\.uv-cache`
- `TEMP=C:\Users\Sulav\Desktop\projects\gridops-intelligence\.tmp`
- `TMP=C:\Users\Sulav\Desktop\projects\gridops-intelligence\.tmp`
- `PYTEST_ADDOPTS=-o cache_dir=.pytest_cache` for pytest

## Commands Run

```powershell
uv run ruff format --check .
uv run ruff format .
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest -q
uv run alembic current
uv run alembic downgrade base
uv run alembic stamp base
uv run alembic upgrade head
uv run alembic current
```

## Exact Results

Initial formatting check:

```text
uv run ruff format --check .
Would reformat: src\gridops\forecasting\runner.py
1 file would be reformatted, 77 files already formatted
```

Formatting:

```text
uv run ruff format .
1 file reformatted, 77 files left unchanged
```

Final formatting check:

```text
uv run ruff format --check .
78 files already formatted
```

Lint:

```text
uv run ruff check .
All checks passed!
```

Typing:

```text
uv run mypy src tests
Success: no issues found in 73 source files
```

Tests:

```text
uv run pytest -q
150 passed, 2 warnings in 18.54s
```

Pytest warnings:

```text
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
PytestCacheWarning: could not create cache path C:\Users\Sulav\Desktop\projects\gridops-intelligence\.pytest_cache\v\cache\nodeids: [WinError 5] Access is denied
```

Alembic current:

```text
uv run alembic current
c1f3a9d7e4b2 (head)
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
```

## Migration Verification

Direct downgrade attempt:

```text
uv run alembic downgrade base
INFO  [alembic.runtime.migration] Running downgrade c1f3a9d7e4b2 -> b2a6d3f4c8e9, Create M04 forecasting foundation.
sqlalchemy.exc.ProgrammingError: (psycopg.errors.UndefinedTable) table "baseline_slice_metric_results" does not exist
```

Reason: integration tests had cleaned ORM tables while `alembic_version` still recorded head, matching the known PostgreSQL test-database mismatch documented in earlier milestone verification.

Clean-schema workaround:

```text
uv run alembic stamp base
INFO  [alembic.runtime.migration] Running stamp_revision c1f3a9d7e4b2 ->
```

Clean upgrade:

```text
uv run alembic upgrade head
INFO  [alembic.runtime.migration] Running upgrade  -> 9c3a87779a9e, Create empty baseline.
INFO  [alembic.runtime.migration] Running upgrade 9c3a87779a9e -> 4f7d9b2a6c1e, Create M02 ingestion storage.
INFO  [alembic.runtime.migration] Running upgrade 4f7d9b2a6c1e -> b2a6d3f4c8e9, Create M03 quality storage.
INFO  [alembic.runtime.migration] Running upgrade b2a6d3f4c8e9 -> c1f3a9d7e4b2, Create M04 forecasting foundation.
```

Final current check:

```text
uv run alembic current
c1f3a9d7e4b2 (head)
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
```

## Feature Snapshot Verification

Automated tests verify:

- forecast issue contract accepts aware UTC issue times
- naive issue times are rejected
- default 24-hour horizons are ordered and hourly
- demand lag features do not use target or future demand
- rolling features do not use future values
- missing lag history produces nulls
- calendar features are deterministic
- weather observation as-of joins ignore observations after issue time
- archived weather forecast joins select latest allowed issue time
- future archived forecast issue times are rejected
- M03 quality-blocked data prevents trusted feature rows
- feature snapshot rows preserve issue time, target interval, lead hour, feature version, and payload lineage

## Baseline Verification

Automated tests verify:

- same-hour-yesterday baseline returns the correct 24-hour historical value
- same-hour-yesterday does not use target or future actual demand
- same-hour-last-week baseline returns the correct 168-hour historical value
- seasonal hourly mean uses only training-window data
- Ridge uses time-based training rows
- Ridge does not use random splitting
- missing history or missing features produce skipped/null predictions

## Backtest Verification

Automated tests verify:

- expanding windows are ordered and deterministic
- rolling windows use the configured rolling training start
- final untouched test-period reservation is represented and respected

## Metric And Slice Verification

Automated tests verify:

- MAE calculation
- RMSE calculation
- WAPE calculation and zero-denominator behavior
- bias calculation
- skipped/null predictions are ignored safely
- slice metrics by lead hour
- slice metrics by target hour and day of week
- persistence of baseline runs, predictions, aggregate metrics, and slice metrics

## Runner Verification

Automated tests verify:

- runner argument parsing works
- dry-run `build-features` output is deterministic
- dry-run `run-backtest` output is deterministic
- dry-run `report` output is deterministic
- report can summarize a prior JSON runner output
- runner does not expose production forecast API behavior

## Known Limitations

- M04 uses fixture-backed/local data foundations.
- Feature payloads are stored as JSON in `feature_snapshot_rows.lineage_metadata`.
- Ridge is a simple baseline only.
- No production forecast model, forecast API, scheduled inference, MLflow registry, prediction intervals, alerts, scenarios, dashboard, or deployment exists.
- No production performance claims are made.

## Completion Gate

M04 completion gate passed in repository state on branch `m04`.
