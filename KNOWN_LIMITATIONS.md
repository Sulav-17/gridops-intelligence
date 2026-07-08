# Known Limitations

## Current Repository

The repository contains the completed M01 foundation:

- project governance and milestone documents
- Python 3.12 package foundation
- uv dependency locking
- Ruff, MyPy, and Pytest configuration
- typed application settings
- structured JSON application logging
- PostgreSQL, SQLAlchemy, Alembic, and Docker Compose foundation
- FastAPI app factory with health and readiness endpoints
- explicit UTC, `America/Toronto`, DST, and IESO hour-ending utilities
- GitHub Actions CI quality gates

## Missing Capabilities

The following are intentionally not implemented yet:

- IESO API clients
- electricity data ingestion
- weather ingestion
- immutable raw source snapshots
- source data-quality checks
- domain tables beyond the empty Alembic baseline
- dbt transformations
- Prefect orchestration
- MLflow tracking
- forecasting models
- operational alerts
- scenario engine
- briefing generation
- frontend or dashboards
- authentication or authorization
- production deployment

## Configuration Limitations

- The default database URL is a local development placeholder.
- No production secret-injection or secret-rotation mechanism exists.
- `.env` support is intended for local development, not production secret management.
- Application settings are instantiated in-process; no deployment configuration layer exists yet.

## Logging Limitations

- Logging currently writes only to a configured stream, normally standard output.
- No centralized log aggregation, persistence, rotation, or retention exists.
- Secret redaction covers recognized field names and common text patterns but cannot guarantee sanitization of every possible secret format.
- Developers must not place credentials in log messages.
- Request IDs, trace IDs, ingestion-run IDs, and other operational correlation fields have not yet been introduced.

## API Limitations

- The FastAPI application has only `/health` and `/ready`.
- There are no domain API routes.
- There is no authentication, authorization, rate limiting, request tracing, or deployment server configuration.
- Readiness verifies basic PostgreSQL connectivity only; it does not validate domain schema readiness because no domain schema exists yet.

## Database Limitations

- The Alembic baseline is intentionally empty.
- No domain tables exist.
- No ingestion, forecast, alert, scenario, or model metadata schema exists.
- Docker Compose is local development infrastructure only.

## Time-Domain Limitations

- IESO hour-ending conversion currently handles the explicit M01 contract only: values 1 through 24 label Toronto local hour endpoints.
- Ambiguous IESO endpoint times are rejected rather than inferred; later ingestion work must preserve enough source context to resolve them intentionally.
- No source-specific parser behavior has been implemented or validated yet.

## Product Limitations

GridOps Intelligence is not intended to:

- dispatch electricity resources
- control grid operations
- declare emergencies
- provide reliability certification
- provide energy-trading advice
- replace IESO forecasts
- perform AC or DC power-flow analysis

## Performance Claims

No forecasting performance claims exist yet. No reliability, uptime, alert-precision, or operational-value claims should be made before verified evaluation.
