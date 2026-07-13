[Live Demo](https://gridops-intelligence.vercel.app/) · [Architecture](ARCHITECTURE.md) · [Case Study](docs/release/CASE_STUDY.md)

# GridOps Intelligence

**Version 1.0.0**

A production-style energy data engineering, forecasting, and decision-support platform for Ontario electricity demand.

GridOps Intelligence turns demand, weather, quality, and model evidence into a clear operational view of the next 24 hours. It helps an analyst answer three practical questions:

1. Which hours need attention?
2. Why are they unusual?
3. How confident is the forecast?

> This is a decision-support demonstration. It does not control the grid, replace IESO forecasts, declare emergencies, or provide trading advice.

## Product overview

The platform preserves source evidence, validates data quality, builds point-in-time-safe features, evaluates demand forecasts, surfaces deterministic alerts, runs bounded planning scenarios, and presents the results in a responsive dashboard.

### Core capabilities

- Fixture-backed IESO demand and weather ingestion with hashes, revisions, source metadata, and raw evidence.
- Persisted data-quality checks, source-health summaries, freshness signals, and blocking logic.
- Leakage-aware feature snapshots, seasonal baselines, ridge evaluation, and time-based backtesting.
- Production forecast outputs with peak, ramp, monitoring, and model-performance foundations.
- Deterministic deviation, ramp, high-demand, and combined-context alerts.
- Bounded weather and load-growth scenario simulations.
- Structured daily briefing facts with explicit evidence.
- FastAPI services and a Next.js dashboard covering forecasts, alerts, quality, scenarios, briefings, model performance, and system status.
- Restricted public demo mode that blocks unsafe mutations while allowing read-only exploration and bounded scenarios.

## System architecture

![GridOps Intelligence system architecture](docs/architecture/system-architecture.svg)

The backend uses Python 3.12, FastAPI, SQLAlchemy, Alembic, and PostgreSQL. The frontend uses Next.js, TypeScript, and Recharts. The browser presents persisted evidence and does not recalculate forecasts, alerts, or operational metrics.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the implemented boundaries, deployment shape, and decision workflow.

## Analyst workflow

![GridOps Intelligence analyst workflow](docs/architecture/analyst-workflow.svg)

This workflow is intentionally evidence-first. Alerts, scenarios, and briefing facts are persisted and traceable before they appear in the dashboard.

## Dashboard areas

- **Overview:** system state, source health, forecast summary, alerts, and briefing status.
- **Forecasts:** hourly demand outlook, peak demand, peak hour, and ramp context.
- **Alerts:** operational attention signals with deterministic evidence.
- **Data quality:** freshness, completeness, continuity, and source-health results.
- **Scenarios:** bounded changes to temperature, humidity, growth, and added load.
- **Briefing:** structured daily analyst facts built from persisted evidence.
- **Model performance:** backtesting and monitoring summaries.
- **System status:** safe operational and demo-mode visibility.

## Verified engineering evidence

The v1.0.0 release verification recorded:

- 219 backend tests passed.
- 25 frontend tests passed.
- Backend formatting, linting, and typing passed.
- Frontend linting, typechecking, and production build passed.
- A clean PostgreSQL migration reached Alembic head.
- API, demo-mode, migration, and Docker smoke checks passed.

See [M07 verification](docs/verification/M07_VERIFICATION.md) and the concise [verification summary](docs/release/VERIFICATION_SUMMARY.md).

## Local setup

### Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Docker
- Node.js 20.9+

### Backend

```powershell
uv sync --all-groups
docker compose up -d postgres
$env:GRIDOPS_DATABASE_URL = "postgresql+psycopg://gridops:gridops@127.0.0.1:55432/gridops"
uv run alembic upgrade head
uv run uvicorn gridops.api:create_app --factory --host 127.0.0.1 --port 8000
```

### Frontend

```powershell
Set-Location frontend
npm.cmd ci
Copy-Item .env.example .env.local
npm.cmd run dev
```

For fixture-backed local demonstration mode, configure:

```text
NEXT_PUBLIC_GRIDOPS_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_GRIDOPS_DEMO_MODE=true
NEXT_PUBLIC_GRIDOPS_USE_DEMO_DATA=true
```

Restart the frontend after changing any `NEXT_PUBLIC_` variable. The dashboard is available at `http://localhost:3000`.

## Public demo mode

Set `GRIDOPS_DEMO_MODE=true` on the backend for a public demonstration. Read endpoints remain available, while alert evaluation, alert lifecycle changes, and briefing generation return `403`. Scenario requests remain available only within configured finite bounds.

Frontend fixture fallback is separate and explicit. It activates only when `NEXT_PUBLIC_GRIDOPS_USE_DEMO_DATA=true` and the backend request fails, and it is visibly labeled in the interface.

## Key API routes

`/health`, `/readiness`, `/dashboard/overview`, `/forecasts/latest`, `/quality/health`, `/alerts`, `/model-performance/latest`, `/system/status`, and `/briefings/latest`.

Dashboard contracts are documented in the [API integration matrix](docs/dashboard/API_INTEGRATION_MATRIX.md).

## Deployment

The supported lightweight deployment shape is:

- Next.js frontend on a Vercel-compatible host.
- Containerized FastAPI backend on a small container platform.
- Managed PostgreSQL.

A public fixture-backed dashboard demo is available on Vercel. It demonstrates the product workflow and interface without claiming live ingestion or production grid operations.

## Screenshots

Screenshots are intentionally not fabricated. Capture the overview, forecast, alerts, quality, scenario, briefing, model-performance, and system-status screens from a locally verified or deployed environment. See the [screenshot guidance](docs/release/screenshots/README.md).

## Known limitations

The project does not include live source ingestion, a production scheduler, authentication, MLflow registry, true prediction intervals, notifications, or verified production reliability. Forecast and scenario outputs must not be treated as official IESO operations.

See [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

## Documentation

- [Architecture](ARCHITECTURE.md)
- [Case study](docs/release/CASE_STUDY.md)
- [Deployment guide](docs/release/DEPLOYMENT_GUIDE.md)
- [Verification summary](docs/release/VERIFICATION_SUMMARY.md)
- [API integration matrix](docs/dashboard/API_INTEGRATION_MATRIX.md)
- [Known limitations](KNOWN_LIMITATIONS.md)

## Portfolio positioning

GridOps Intelligence demonstrates production-minded data engineering, time-series evaluation, API design, MLOps foundations, operational safety boundaries, release verification, and decision-support UX in one end-to-end system.
