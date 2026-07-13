# GridOps Intelligence

**Version 1.0.0** — a production-style energy data engineering, forecasting, and decision-support portfolio project for Ontario electricity demand.

GridOps Intelligence demonstrates a transparent workflow for preserving source evidence, validating data quality, evaluating demand forecasts, surfacing deterministic operational attention signals, running bounded planning simulations, and presenting persisted evidence in a responsive dashboard.

It is a decision-support demonstration, not a grid-control system. It does not replace IESO forecasts, declare emergencies, provide trading advice, or control electricity infrastructure.

## What it demonstrates

- Fixture-backed IESO demand and weather ingestion with raw-evidence metadata, hashes, revisions, and source-native time fields.
- Persisted source-health checks and safe quality summaries.
- Leakage-aware feature snapshots, baseline backtesting, and persisted evaluation metrics.
- Local model artifact, model-selection, forecast-output, monitoring, peak, and ramp foundations.
- Deterministic alert evidence, bounded scenario simulations, and structured briefing facts.
- A Next.js dashboard for overview, forecasts, alerts, data quality, scenarios, briefings, model performance, and safe system status.
- A configurable public demo mode that blocks alert mutation and briefing generation while allowing bounded scenarios.

## Architecture

```text
Fixture inputs -> raw evidence + PostgreSQL -> quality + feature snapshots
                -> forecast / monitoring evidence -> alerts / scenarios / briefings
                -> FastAPI API -> Next.js dashboard
```

The backend is Python 3.12, FastAPI, SQLAlchemy, Alembic, and PostgreSQL. The dashboard is Next.js, TypeScript, and Recharts. More detail is in [Architecture](ARCHITECTURE.md).

## Screens

Screenshots are intentionally not fabricated. Capture the documented dashboard screens from a locally verified or deployed environment; see [screenshot guidance](docs/release/screenshots/README.md).

## Local setup

Prerequisites: Python 3.12, [uv](https://docs.astral.sh/uv/), Docker, and Node.js 20.9+.

```powershell
uv sync --all-groups
docker compose up -d postgres
$env:GRIDOPS_DATABASE_URL = "postgresql+psycopg://gridops:gridops@127.0.0.1:55432/gridops"
uv run alembic upgrade head
uv run uvicorn gridops.api:create_app --factory --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
Set-Location frontend
npm.cmd ci
$env:NEXT_PUBLIC_GRIDOPS_API_BASE_URL = "http://127.0.0.1:8000"
npm.cmd run dev
```

The dashboard is available at `http://localhost:3000`. See the [deployment guide](docs/release/DEPLOYMENT_GUIDE.md) for demo mode, CORS, migrations, containers, and troubleshooting.

## Demo mode

Set `GRIDOPS_DEMO_MODE=true` on the backend to protect public demonstrations. Read endpoints remain available; alert evaluation, alert lifecycle changes, and briefing generation return `403`. Scenario requests are accepted only inside configured finite bounds. The frontend uses fixture-backed fallback only when `NEXT_PUBLIC_GRIDOPS_USE_DEMO_DATA=true`, and labels it clearly.

## APIs and dashboard

Key read routes are `/health`, `/readiness`, `/dashboard/overview`, `/forecasts/latest`, `/quality/health`, `/alerts`, `/model-performance/latest`, `/system/status`, and `/briefings/latest`. Dashboard-facing contracts are documented in [the API integration matrix](docs/dashboard/API_INTEGRATION_MATRIX.md).

## Verification

Release verification, exact command outputs, migration evidence, API smoke checks, and dependency-review results are recorded in [M07 verification](docs/verification/M07_VERIFICATION.md) and the concise [verification summary](docs/release/VERIFICATION_SUMMARY.md).

## Deployment path

The supported lightweight path is a Vercel-compatible Next.js frontend, a containerized FastAPI service on a simple container platform, and managed PostgreSQL. Deployment requires operator-provided hosting and database credentials; no live production deployment is claimed by this repository.

## Limitations

The project has no live source ingestion, scheduler, authentication, MLflow registry, true prediction intervals, notification system, or verified production reliability claim. Forecast and scenario outputs must not be treated as official IESO operations. See [Known limitations](KNOWN_LIMITATIONS.md).

## Portfolio positioning

GridOps Intelligence is designed to demonstrate production-minded data engineering, time-series evaluation, API design, MLOps foundations, safety boundaries, release verification, and honest operational UX. The [case study](docs/release/CASE_STUDY.md) explains the design and evidence in more detail.
