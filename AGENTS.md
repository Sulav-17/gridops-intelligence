# AGENTS.md

## Role

You are implementing the remaining M01 foundation work for GridOps Intelligence.

Work carefully, keep scope tight, and do not introduce future milestone features.

## Current Status

Already completed and merged into `m01`:

- M01-T01 Repository and Python Foundation
- M01-T02 Configuration and Structured Logging
- M01-T04 PostgreSQL, SQLAlchemy, Alembic, and Docker

Remaining work to complete in one pass:

- M01-T03 FastAPI application foundation
- M01-T05 UTC, Toronto time, DST, and IESO hour-ending contract
- M01-T06 GitHub Actions CI quality gates
- M01-T07 full verification, consolidated documentation, and handoff

## Hard Scope Boundaries

Do not implement:

- data ingestion
- IESO API clients
- weather ingestion
- raw data snapshots
- dbt
- Prefect
- MLflow
- forecasting models
- alerts
- scenarios
- frontend
- dashboards
- authentication
- production deployment
- domain tables beyond the empty Alembic baseline

## Required Implementation

### FastAPI

Add a small FastAPI foundation.

Required behavior:

- app factory
- `/health` endpoint
- `/ready` endpoint
- `/health` does not touch the database
- `/ready` checks real PostgreSQL connectivity
- readiness failures must return a safe 503 response without leaking secrets
- use existing `Settings`, logging, and database foundation
- include tests

Suggested files:

- `src/gridops/api.py`
- `tests/test_api.py`

### Time Contract

Add explicit time utilities and tests.

Required behavior:

- canonical timestamps are timezone-aware UTC
- Toronto local time uses `America/Toronto`
- naive datetimes are rejected
- UTC to Toronto conversion is tested
- Toronto to UTC conversion is tested
- DST spring-forward behavior is tested
- DST fall-back behavior is tested
- IESO hour-ending values are validated
- IESO hour-ending conversion is documented and tested
- ambiguous or nonexistent local times must not be silently guessed

Suggested files:

- `src/gridops/time_utils.py`
- `tests/test_time_utils.py`

Use only Python standard library time-zone support unless there is a strong reason otherwise.

### CI

Add GitHub Actions CI.

Required checks:

- Python 3.12
- uv install
- Ruff format check
- Ruff lint
- MyPy
- Pytest
- PostgreSQL available for integration tests

Suggested file:

- `.github/workflows/ci.yml`

Use Docker Compose if easiest.

### Final Documentation

Only update documentation at the end.

Update:

- `README.md`
- `ARCHITECTURE.md`
- `DECISIONS.md`
- `KNOWN_LIMITATIONS.md`
- `CURRENT_STATE.md`

Documentation must summarize the full completed M01 foundation and clearly state what is not implemented yet.

## Quality Gate

Before finishing, run:

```powershell
uv run ruff format .
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest -q

$env:GRIDOPS_DATABASE_URL = "postgresql+psycopg://gridops:gridops@127.0.0.1:55432/gridops_test"
uv run alembic current
Remove-Item Env:\GRIDOPS_DATABASE_URL

git diff --check
git status --short