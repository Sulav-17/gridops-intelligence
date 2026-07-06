# Known Limitations

## Current Repository

The repository currently contains project-planning and governance documents only.

No executable application has been implemented.

## Current Missing Capabilities

The following do not yet exist:

- Python package
- FastAPI service
- health endpoint
- readiness endpoint
- PostgreSQL environment
- database schema
- SQLAlchemy configuration
- Alembic migrations
- Docker Compose environment
- automated tests
- CI workflow
- source ingestion
- data-quality checks
- forecasting models
- MLflow tracking
- operational alerts
- scenario engine
- dashboard
- deployment

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