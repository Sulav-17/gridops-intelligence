# GridOps Intelligence Architecture

## Document Status

This document distinguishes between approved target architecture and architecture actually implemented. Planned components are not described as complete until they exist in the repository.

## Current Implemented Architecture

M01 and M02 are implemented.

### Foundation

- Python 3.12 project using a `src` layout
- uv dependency management and lockfile
- Ruff, MyPy, and Pytest
- typed Pydantic Settings with `GRIDOPS_` prefix
- structured JSON logging with UTC timestamps and secret redaction
- synchronous SQLAlchemy engine and session helpers
- PostgreSQL as the primary relational database
- Alembic migrations
- Docker Compose PostgreSQL on host port `55432`
- FastAPI app factory with `/health` and `/ready`
- explicit UTC, Toronto time, DST, and IESO hour-ending utilities

### M02 Ingestion Foundation

Bronze storage:

- `ingestion_runs`
- `raw_snapshots`
- local raw payload files stored by source and SHA-256 hash

Silver storage:

- `ieso_hourly_demand`
- `weather_observations`
- `weather_forecasts`

Ingestion code:

- source registry contract
- SHA-256 hashing utility
- raw snapshot storage abstraction
- fixture-backed IESO hourly demand parser and loader
- fixture-backed weather observation parser and loader
- fixture-backed archived weather forecast parser and loader
- simple fixture runner through `python -m gridops.ingestion.runner`

Silver rows retain raw snapshot IDs, ingestion run IDs, source-native fields, normalized UTC timestamps, row hashes, `is_current`, and `superseded_at_utc`.

## Approved Target Architecture

The planned system flow is:

1. IESO, weather, and calendar sources
2. ingestion workflows
3. immutable raw snapshots
4. validation, normalization, and revision handling
5. PostgreSQL warehouse
6. dbt transformations where useful
7. point-in-time feature snapshots
8. leakage-safe backtesting
9. MLflow experiment tracking and model registry
10. scheduled inference
11. forecast, quality, alert, scenario, and briefing services
12. FastAPI backend
13. Next.js operational dashboard

## Current Boundaries

M02 does not implement live source fetching, Prefect orchestration, dbt transformations, formal data-quality severity checks, gold feature tables, forecasting, MLflow, alerts, scenarios, dashboard work, or deployment.
