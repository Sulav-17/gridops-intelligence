# GridOps Intelligence Architecture

## Document Status

This document distinguishes between approved target architecture and architecture actually implemented. Planned components are not described as complete until they exist in the repository.

## Current Implemented Architecture

M01 - Domain Contract and Foundation is implemented.

### Python Foundation

- Python 3.12 project
- src-based `gridops` package
- uv dependency management and lockfile
- Ruff formatting and linting
- strict MyPy checking
- Pytest test foundation

### Configuration

- strongly typed Pydantic Settings model
- `GRIDOPS_` environment-variable prefix
- optional local `.env` loading
- typed application environment and log-level values
- validated API host, port, and readiness timeout
- PostgreSQL-only database URL validation
- secret-safe database URL representation

### Logging

- Python standard-library logging
- one-line structured JSON output
- UTC timestamps
- configurable severity
- stable application logger name
- idempotent logger initialization
- structured context fields
- recognized credential-field redaction
- common credential-pattern sanitization

### Database Foundation

- PostgreSQL is the primary relational database
- Docker Compose provides local PostgreSQL on host port 55432
- SQLAlchemy synchronous engine and session factory
- SQLAlchemy declarative base with deterministic naming conventions
- transactional session scope helper
- real connectivity check used by readiness behavior
- Alembic configured with an empty baseline migration

### API Foundation

- FastAPI application factory in `gridops.api`
- `/health` process-health endpoint
- `/ready` PostgreSQL readiness endpoint
- health checks avoid database access
- readiness failures return safe `503` JSON without connection details or credentials
- application setup uses existing settings, logging, and database foundation

### Time Foundation

- canonical timestamps use timezone-aware UTC
- Ontario local time uses `America/Toronto`
- naive datetimes are rejected
- UTC-to-Toronto and Toronto-to-UTC conversions are tested
- nonexistent spring-forward wall times are rejected
- ambiguous fall-back wall times require explicit fold selection
- IESO hour-ending values are validated from 1 through 24
- IESO hour-ending conversion maps the label to the end of the Toronto local operating hour

### CI

- GitHub Actions workflow runs on Python 3.12
- uv installs locked dependencies
- PostgreSQL service is available for integration tests
- CI runs Ruff format check, Ruff lint, MyPy, Pytest, and Alembic current

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

## Planned Data Layers

Bronze preserves source evidence such as original payloads, source URLs, publication times, retrieval times, hashes, parser versions, and ingestion-run identifiers.

Silver normalizes source data while retaining source meaning, including UTC timestamps, Ontario local-time interpretation, source-native date and time fields, IESO hour-ending values, normalized units, revision metadata, and quality flags.

Gold supports operational and analytical use through demand facts, weather features, model feature snapshots, forecasts, prediction intervals, evaluation metrics, alerts, scenarios, and briefing facts.

## M01 Architectural Boundary

M01 establishes package structure, configuration, logging, PostgreSQL connectivity, SQLAlchemy, Alembic, Docker Compose, FastAPI health and readiness behavior, CI, and time-domain contracts.

M01 does not implement real IESO ingestion, weather ingestion, Prefect flows, dbt models, training datasets, forecasting models, MLflow, alert logic, scenario logic, frontend features, authentication, or production deployment.
