# Known Limitations

## Current Repository

The repository contains:

- project governance and milestone documents
- a Python 3.12 package foundation
- dependency locking through uv
- formatting, linting, typing, and test configuration
- strongly typed application settings
- structured JSON application logging
- automated configuration and logging tests

The repository does not yet contain a runnable API or database environment.

## Current Missing Capabilities

The following do not yet exist:

- FastAPI service
- health endpoint
- readiness endpoint
- PostgreSQL runtime environment
- database schema
- SQLAlchemy configuration
- Alembic migrations
- Docker Compose environment
- GitHub Actions CI
- source ingestion
- data-quality checks
- forecasting models
- MLflow tracking
- operational alerts
- scenario engine
- dashboard
- deployment

## Configuration Limitations

- The default database URL is a local development placeholder.
- No live PostgreSQL connection is attempted during configuration creation.
- Application settings are instantiated directly; a shared application lifecycle has not yet been created.
- Production secret injection and secret rotation are not implemented.
- `.env` support is intended for local development, not production secret management.

## Logging Limitations

- Logging currently writes only to a configured stream, normally standard output.
- No centralized log aggregation, persistence, rotation, or retention exists.
- Secret redaction covers recognized field names and common text patterns but cannot guarantee sanitization of every possible secret format.
- Developers must not place credentials in log messages.
- Request IDs, trace IDs, ingestion-run IDs, and other operational correlation fields have not yet been introduced.
- Logging has not yet been connected to FastAPI or background workflows.

## Domain Limitations

The exact implementation of IESO hour-ending conversion has not yet been established.

Ontario daylight-saving behavior has not yet been implemented or tested.

No assumptions about source behavior should be treated as verified until M01 and M02 evidence exists.

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

No forecasting performance claims exist yet.

No reliability, uptime, alert-precision, or operational-value claims should be made before verified evaluation.