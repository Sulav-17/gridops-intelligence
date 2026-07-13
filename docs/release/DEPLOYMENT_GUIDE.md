# Deployment Guide

## Supported deployment path

Deploy the Next.js dashboard to Vercel or another compatible Node.js host. Deploy the FastAPI `Dockerfile` to a small container platform and use managed PostgreSQL. This repository does not include hosting credentials, infrastructure provisioning, or a claim of a live production deployment.

## Prerequisites

- Python 3.12 and uv for local backend work.
- Node.js 20.9+ and npm for the frontend.
- Docker for local PostgreSQL and container validation.
- A managed PostgreSQL instance and two HTTPS origins for a hosted environment.

## Local backend

```powershell
uv sync --all-groups
docker compose up -d postgres
$env:GRIDOPS_DATABASE_URL = "postgresql+psycopg://gridops:gridops@127.0.0.1:55432/gridops"
uv run alembic upgrade head
uv run uvicorn gridops.api:create_app --factory --host 127.0.0.1 --port 8000
```

Use `/health` for a process probe and `/readiness` for PostgreSQL readiness. `/ready` remains as a compatibility alias.

## Local frontend

```powershell
Set-Location frontend
npm.cmd ci
Copy-Item .env.example .env.local
npm.cmd run dev
```

For local fixture mode, edit `frontend/.env.local` to set:

```text
NEXT_PUBLIC_GRIDOPS_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_GRIDOPS_DEMO_MODE=true
NEXT_PUBLIC_GRIDOPS_USE_DEMO_DATA=true
```

Restart `npm.cmd run dev` after changing any `NEXT_PUBLIC_` variable, then hard refresh the browser. Fixture fallback remains explicit and is selected only after a backend request fails; it does not replace a successful backend response or silently activate in production. The dashboard runs at `http://localhost:3000`.

## Environment variables

Backend:

- `GRIDOPS_APP_ENVIRONMENT=production`
- `GRIDOPS_DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>/<database>`
- `GRIDOPS_CORS_ALLOWED_ORIGINS=https://<frontend-host>`
- `GRIDOPS_DEMO_MODE=true` for a restricted public demonstration
- `GRIDOPS_DEMO_SCENARIO_*_LIMIT` to adjust public simulation bounds

Frontend:

- `NEXT_PUBLIC_GRIDOPS_API_BASE_URL=https://<api-host>`
- `NEXT_PUBLIC_GRIDOPS_DEMO_MODE=true` when the public API is in demo mode
- `NEXT_PUBLIC_GRIDOPS_USE_DEMO_DATA=true` only for an explicit fixture-backed fallback

Never publish database URLs, passwords, tokens, `.env` files, raw source data, or local artifacts. `.env.example` files contain safe placeholders only.

## CORS

Set the backend CORS value to the exact deployed frontend origin, without a trailing slash. Local defaults allow `http://localhost:3000` and `http://127.0.0.1:3000`. A wildcard is rejected in the `production` app environment. CORS is not authentication: the public demo must be treated as an unprotected read-only/restricted experience.

## Migrations

Run migrations as a one-off release step before starting a new backend image:

```sh
uv run alembic upgrade head
uv run alembic current
```

Use the same `GRIDOPS_DATABASE_URL` as the application. The release process does not run migrations automatically at web-process startup.

## Container build and startup

```powershell
docker build -t gridops-intelligence-api:1.0.0 .
docker run --rm -p 8000:8000 --env-file .env gridops-intelligence-api:1.0.0
```

The image uses a non-root `gridops` user and starts `uvicorn gridops.api:create_app --factory --host 0.0.0.0 --port 8000`. It excludes local raw data, artifacts, caches, tests, frontend dependencies, and environment files.

## Public demo mode and fixture fallback

With backend demo mode enabled, `POST /alerts/evaluate`, `PATCH /alerts/{id}/state`, and `POST /briefings/generate` return `403`. Bounded scenario requests remain available. Backend records may be empty until persisted data is seeded; `404` or empty states are expected in that case.

Fixture fallback is a frontend-only demonstration option. It requires `NEXT_PUBLIC_GRIDOPS_USE_DEMO_DATA=true`, uses typed fixture contracts, and is visibly labeled. It is never evidence of live ingestion.

## Verification and troubleshooting

Run the release commands in [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md). Confirm `/health` and `/readiness` after deployment, then verify the configured frontend origin receives a CORS response.

If the API returns `503`, inspect safe application logs and PostgreSQL connectivity without exposing URLs or credentials. If browser requests fail, compare the exact `NEXT_PUBLIC_GRIDOPS_API_BASE_URL` and `GRIDOPS_CORS_ALLOWED_ORIGINS` values. Roll back by redeploying the previous known-good frontend/API images after confirming their database-migration compatibility; do not reverse schema changes without a separately reviewed migration plan.

## Current frontend audit exception

The locked production tree contains `next@16.2.10`, which pins transitive `postcss@8.4.31` for its CSS webpack build block. npm reports `GHSA-qx2v-qp2m-jg93` (npm advisory source `1117015`) for PostCSS versions below `8.5.10`; patched PostCSS versions begin at `8.5.10`. The separate Vite/Vitest development path resolves patched `postcss@8.5.17` and is omitted from the production audit.

`next@16.2.10` is the current stable registry release, and the audit marks the affected Next range as `9.3.4-canary.0 - 16.3.0-canary.5`. A safe `npm install` refresh left the dependency tree unchanged. No direct PostCSS dependency or override is added: Next pins `8.4.31` exactly, so forcing `8.5.18` would be an unsupported compatibility assumption. Do not use `npm audit fix --force`, which proposes the breaking downgrade `next@9.3.3`.
