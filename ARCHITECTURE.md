# GridOps Intelligence Architecture

## Product boundary

GridOps Intelligence is an evidence-oriented Ontario electricity-demand decision-support application. It preserves and presents analytical records; it does not operate the grid or make official operational declarations.

## Implemented system

```text
Fixture CSV sources
  -> ingestion runs + raw snapshots + normalized PostgreSQL facts
  -> persisted quality checks and source-health summaries
  -> point-in-time feature snapshots and forecast evaluation
  -> local model artifacts, production forecast outputs, monitoring summaries
  -> deterministic alerts, scenarios, and briefing facts
  -> FastAPI read/write API with demo-mode restrictions
  -> Next.js dashboard or explicit fixture-backed fallback
```

### Storage and services

- PostgreSQL is the system of record. Alembic owns schema history.
- Source evidence includes ingestion metadata, content hashes, source-native fields, normalized UTC timestamps, and revision state.
- Canonical timestamps are timezone-aware UTC. Dashboard presentation uses `America/Toronto`; IESO hour-ending fields are preserved separately.
- Quality, forecast, alert, scenario, and briefing records are persisted before presentation. Browser pages do not recalculate metrics, forecasts, or alert evidence.

### Backend

The Python 3.12 backend uses FastAPI, Pydantic Settings, SQLAlchemy 2.x, Alembic, and PostgreSQL. `/health` is a process probe; `/readiness` verifies PostgreSQL safely. Browser CORS origins are configured with `GRIDOPS_CORS_ALLOWED_ORIGINS` and cannot be wildcarded in production.

Public demo mode (`GRIDOPS_DEMO_MODE=true`) keeps reads available but returns `403` for alert evaluation, alert state changes, and briefing generation. Scenarios remain available only after server-side finite-value and configured-bound validation.

### Dashboard

The Next.js App Router dashboard has pages for overview, forecasts, alerts and detail, data quality, scenarios, briefing, model performance, system status, and product documentation. `NEXT_PUBLIC_GRIDOPS_API_BASE_URL` configures the API. Fixture fallback requires the separate explicit setting `NEXT_PUBLIC_GRIDOPS_USE_DEMO_DATA=true` and is visibly labeled.

### Deployment shape

The repository supplies a non-root FastAPI container image. The documented deployment path is a Vercel-compatible frontend, a small container platform for the API, and managed PostgreSQL. No hosted environment or live ingestion deployment is asserted.

## Deliberately absent

No live source client, scheduler, Prefect flow, dbt project, MLflow registry, authentication, notification service, true quantile model, or grid-control capability is implemented. See [Known limitations](KNOWN_LIMITATIONS.md).
