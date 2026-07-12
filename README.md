# GridOps Intelligence

GridOps Intelligence is a production-style energy data engineering, forecasting, and MLOps platform focused on Ontario electricity demand.

The system is intended to ingest public electricity and weather data, preserve source evidence, validate and normalize changing source data, produce trusted day-ahead forecasting evaluations, and support production forecasting, alerts, scenarios, APIs, and an operational dashboard.

M06 is complete. M07 is active on branch `m07`.

## Current Status

Completed milestones:

- M01 - Foundation and environment readiness
- M02 - Data ingestion foundation
- M03 - Data quality and observability
- M04 - Baselines and backtesting
- M05 - Production Forecasting and MLOps
- M06 - Alerts, Scenarios, and Briefings

M07 work in progress:

- C01 - dashboard integration APIs and demo-mode protections
- C02 - Next.js dashboard foundation for overview, forecasts, data quality, model performance, and system status

Implemented foundation:

- Python 3.12 src-based package managed by uv
- Ruff formatting and linting
- strict MyPy
- Pytest
- typed `GRIDOPS_` configuration with secret-aware database URL handling
- structured JSON logging with UTC timestamps and defensive redaction
- synchronous SQLAlchemy database foundation
- Alembic migrations
- Docker Compose PostgreSQL on host port `55432`
- FastAPI app factory with `/health`, `/ready`, and `GET /quality/health`
- UTC, `America/Toronto`, DST, and IESO hour-ending utilities
- fixture-backed ingestion for IESO demand, weather observations, and archived weather forecasts
- persisted data quality checks, quality runs, quality results, blocking decisions, and source-health summaries
- forecast issue contracts and deterministic hourly horizons
- point-in-time feature snapshots with leakage-safe demand, calendar, weather observation, and archived forecast features
- same-hour-yesterday, same-hour-last-week, seasonal hourly mean, and Ridge baselines
- deterministic rolling or expanding backtest window definitions
- MAE, RMSE, WAPE, bias, and slice metric calculations
- persisted baseline run, prediction, aggregate metric, and slice metric rows
- simple forecasting runner previews through `python -m gridops.forecasting.runner`
- M05 production forecasting and MLOps schema contracts for model training runs, artifacts, model selection, production forecasts, peak/ramp outputs, and monitoring summaries
- local model artifact save/load utilities with SHA-256 hashes and metadata persistence
- model-selection gate logic comparing candidate MAE and WAPE against selected M04 baseline metrics
- deterministic sklearn candidate training from persisted M04 feature snapshots, with artifact persistence and model-selection results
- production forecast generation foundation from selected model artifacts, including P50 predictions, peak output, ramp outputs, and lineage
- model performance and drift monitoring foundations persisted to M05 summary tables
- simple M05 production runner boundaries through `python -m gridops.forecasting.production_runner`
- M06 alert foundation with deterministic alert contracts, fixed-threshold high-demand/ramp/deviation rules, M03 source-health context alerts, combined context alerts, duplicate-active alert prevention, immutable evidence, and lifecycle history
- M06 scenario and briefing foundation with deterministic scenario calculations, persisted assumptions/results, deterministic briefing facts, and backend scenario/briefing endpoints
- M06 alert API endpoints and simple decision runner commands

Not implemented yet:

- live source fetching
- orchestration with Prefect
- dbt transformations
- production forecast API or model serving
- true quantile models or prediction intervals
- MLflow registry
- scheduled inference
- alert, scenario, and briefing dashboard screens
- authentication or deployment

## Local Development

Requirements:

- Git
- uv
- Python 3.12
- Docker, for PostgreSQL-backed checks

Install dependencies:

```powershell
uv sync --all-groups
```

Start PostgreSQL:

```powershell
docker compose up -d postgres
```

The local PostgreSQL service maps host port `55432` to container port `5432`. The default application database is `gridops`; the Docker init script creates `gridops_test` for integration tests when the volume is first initialized.

Run quality checks:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest -q
```

Run Alembic against the test database:

```powershell
$env:GRIDOPS_DATABASE_URL = "postgresql+psycopg://gridops:gridops@127.0.0.1:55432/gridops_test"
uv run alembic current
Remove-Item Env:\GRIDOPS_DATABASE_URL
```

## Ingestion And Quality

Run fixture ingestion:

```powershell
$env:GRIDOPS_DATABASE_URL = "postgresql+psycopg://gridops:gridops@127.0.0.1:55432/gridops_test"
uv run alembic upgrade head
uv run python -m gridops.ingestion.runner --source ieso-demand --mode fixture --path tests/fixtures/ingestion/ieso/hourly_demand_sample.csv
uv run python -m gridops.ingestion.runner --source weather-observations --mode fixture --path tests/fixtures/ingestion/weather/observations_sample.csv
uv run python -m gridops.ingestion.runner --source weather-forecasts --mode fixture --path tests/fixtures/ingestion/weather/forecasts_sample.csv
Remove-Item Env:\GRIDOPS_DATABASE_URL
```

Run persisted quality checks:

```powershell
$env:GRIDOPS_DATABASE_URL = "postgresql+psycopg://gridops:gridops@127.0.0.1:55432/gridops_test"
uv run python -m gridops.quality.runner --dataset ieso_hourly_demand
uv run python -m gridops.quality.runner --dataset weather_observations
uv run python -m gridops.quality.runner --dataset weather_forecasts
uv run python -m gridops.quality.runner --dataset raw_snapshots
uv run python -m gridops.quality.runner --dataset ingestion_runs
Remove-Item Env:\GRIDOPS_DATABASE_URL
```

## Forecasting Evaluation

Preview feature snapshot generation:

```powershell
uv run python -m gridops.forecasting.runner build-features --forecast-issue-time-utc 2026-07-09T15:00:00Z --horizon-hours 24 --dry-run
```

Persist feature snapshots against the configured database:

```powershell
$env:GRIDOPS_DATABASE_URL = "postgresql+psycopg://gridops:gridops@127.0.0.1:55432/gridops_test"
uv run python -m gridops.forecasting.runner build-features --forecast-issue-time-utc 2026-07-09T15:00:00Z --horizon-hours 24
Remove-Item Env:\GRIDOPS_DATABASE_URL
```

Preview deterministic backtest windows:

```powershell
uv run python -m gridops.forecasting.runner run-backtest --training-start-utc 2026-07-01T00:00:00Z --start-utc 2026-07-08T00:00:00Z --end-utc 2026-07-10T00:00:00Z --minimum-training-history-hours 24 --dry-run
```

Summarize forecasting capabilities:

```powershell
uv run python -m gridops.forecasting.runner report --dry-run
```

## Production Forecasting Foundation

Preview deterministic candidate training:

```powershell
uv run python -m gridops.forecasting.production_runner train-candidate --feature-version m04_c01_foundation --training-start-utc 2026-01-01T00:00:00Z --training-end-utc 2026-02-01T00:00:00Z --evaluation-start-utc 2026-02-01T00:00:00Z --evaluation-end-utc 2026-02-08T00:00:00Z --selected-baseline-name same_hour_yesterday --dry-run
```

Preview forecast generation from a selected artifact:

```powershell
uv run python -m gridops.forecasting.production_runner generate-forecast --model-artifact-id 1 --forecast-issue-time-utc 2026-02-09T10:00:00Z --dry-run
```

Preview monitoring summaries:

```powershell
uv run python -m gridops.forecasting.production_runner summarize-monitoring --model-artifact-id 1 --evaluation-start-utc 2026-02-01T00:00:00Z --evaluation-end-utc 2026-02-02T00:00:00Z --baseline-start-utc 2026-01-01T00:00:00Z --baseline-end-utc 2026-01-02T00:00:00Z --comparison-start-utc 2026-02-01T00:00:00Z --comparison-end-utc 2026-02-02T00:00:00Z --dry-run
```

These commands are deterministic runner boundaries, not a scheduler or production serving API.

## API Foundation

Create the FastAPI app with:

```python
from gridops.api import create_app

app = create_app()
```

Endpoints:

- `GET /health` returns process health and does not touch the database.
- `GET /ready` checks real PostgreSQL connectivity and returns a safe `503` response when the dependency is unavailable.
- `GET /quality/health` summarizes latest persisted quality status, worst severity, blocking state, check counts, and safe failure summaries for supported datasets.
- `GET /alerts` lists persisted alerts and current evidence.
- `GET /alerts/{alert_id}` returns alert evidence and lifecycle history.
- `POST /alerts/evaluate` evaluates deterministic alert rules for a production forecast run.
- `PATCH /alerts/{alert_id}/state` applies a validated lifecycle transition.
- `POST /scenarios` runs a deterministic decision-support scenario.
- `GET /scenarios/{scenario_id}` returns persisted scenario assumptions and result rows.
- `POST /briefings/generate` creates deterministic briefing facts.
- `GET /briefings/latest` returns the latest persisted briefing.

Dashboard integration endpoints:

- `GET /dashboard/overview` returns the compact persisted operational summary.
- `GET /forecasts/latest` and `GET /forecasts/{forecast_run_id}` return persisted production forecast outputs.
- `GET /model-performance/latest` returns persisted baseline, performance, and drift evidence.
- `GET /system/status` returns safe readiness and latest-run timestamps.

Demo mode blocks alert mutation and briefing generation, while bounded scenario execution remains available. See `docs/dashboard/API_INTEGRATION_MATRIX.md` for the public integration contract.

## Frontend Dashboard

The M07-C02 dashboard lives in `frontend/`. It uses the Next.js App Router, TypeScript, Recharts, ESLint, and Vitest. Node.js 20.9 or later is required; the frontend package uses npm.

Install and start it locally:

```powershell
Set-Location frontend
npm.cmd install
npm.cmd run dev
```

Validate the frontend:

```powershell
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run test
npm.cmd run build
```

Copy `frontend/.env.example` to a local `.env.local` and set `NEXT_PUBLIC_GRIDOPS_API_BASE_URL` to the backend's public base URL. `NEXT_PUBLIC_GRIDOPS_DEMO_MODE=true` labels the UI as a public demo. `NEXT_PUBLIC_GRIDOPS_USE_DEMO_DATA=true` allows an explicit fixture-backed fallback only when the backend cannot be reached; this data is synthetic demonstration data, not live IESO data.

Implemented frontend screens are Overview, Forecasts, Alerts (including persisted evidence and lifecycle detail), Data Quality, Scenarios, Briefing, Model Performance, System Status, and the limitations documentation page. Alerts and Briefing are read-only in the public UI. Scenarios are bounded simulations, not forecasts; public demo bounds are load growth -10 to +10 percent, added load -2,000 to +2,000 MW, temperature -10 to +10 C, and humidity -30 to +30 percent. Weather adjustment is a deterministic approximation, and stored humidity assumptions do not change simulated values. Fixture fallback is explicitly labeled and never represents live IESO ingestion. The C03 frontend tests cover alert evidence/history, scenario validation and server failures, briefing states, fixture labels, and the absence of public mutation, ingestion, training, inference, or model-promotion controls.

`npm.cmd audit --omit=dev` could not reach the npm audit endpoint from the local verification environment on July 12, 2026; this is a known verification-environment limitation, not a claim that dependencies have no advisories. M07-C04 remains responsible for deployment, release artifacts, and final milestone verification; M07 is not complete.

## Decision Support Runner

Evaluate alerts:

```powershell
uv run python -m gridops.decision.runner evaluate-alerts --forecast-run-id 1
```

Run a demand-growth scenario:

```powershell
uv run python -m gridops.decision.runner run-scenario --forecast-run-id 1 --load-growth-percent 2
```

Generate briefing facts:

```powershell
uv run python -m gridops.decision.runner generate-briefing --forecast-run-id 1
```

## Time Contract

Time utilities live in `gridops.time_utils`.

- canonical timestamps are timezone-aware UTC
- Ontario local time uses `America/Toronto`
- naive datetimes are rejected
- ambiguous fall-back Toronto wall times require an explicit `fold`
- nonexistent spring-forward Toronto wall times are rejected
- IESO hour-ending values are valid only from 1 through 24
- IESO hour-ending values label the end of an operating hour in Toronto local time

## Project Documents

| Document | Purpose |
|---|---|
| `PROJECT_RULES.md` | Permanent project execution rules |
| `CURRENT_STATE.md` | Current verified repository status |
| `ROADMAP.md` | Seven-milestone delivery plan |
| `ARCHITECTURE.md` | Architecture actually implemented or formally approved |
| `DECISIONS.md` | Important architectural and project decisions |
| `KNOWN_LIMITATIONS.md` | Honest limitations and deferred work |
| `docs/data/SOURCE_CONTRACTS.md` | M02 fixture source contracts and assumptions |
| `docs/data/INGESTION_RUNBOOK.md` | M02 fixture ingestion commands and operations |
| `docs/quality/QUALITY_CONTRACTS.md` | M03 dataset quality contracts, thresholds, and blocking rules |
| `docs/quality/QUALITY_RUNBOOK.md` | M03 quality runner usage and troubleshooting |
| `docs/forecasting/FORECAST_ISSUE_CONTRACT.md` | M04 forecast issue and horizon contract |
| `docs/forecasting/FEATURE_SNAPSHOT_CONTRACT.md` | M04 point-in-time feature snapshot contract |
| `docs/forecasting/BACKTESTING_RUNBOOK.md` | M04 forecasting runner and backtesting runbook |
| `docs/forecasting/BASELINE_REPORT.md` | M04 baseline evaluation report |
| `docs/forecasting/MODEL_TRAINING_RUNBOOK.md` | M05 candidate training workflow |
| `docs/forecasting/MODEL_SELECTION.md` | M05 model-selection gate behavior |
| `docs/forecasting/FORECAST_OUTPUT_CONTRACT.md` | M05 production forecast output contract |
| `docs/decision/ALERT_RULES.md` | M06 alert rule contracts, thresholds, lifecycle, evidence, and limitations |
| `docs/decision/SCENARIO_RUNBOOK.md` | M06 scenario assumptions, calculations, persistence, API usage, and limitations |
| `docs/decision/BRIEFING_RUNBOOK.md` | M06 deterministic briefing fact sources, API usage, unsupported claims, and limitations |
| `docs/verification/M04_VERIFICATION.md` | M04 verification evidence and exact command results |
| `docs/handoffs/M04_HANDOFF.md` | M04 completion handoff for M05 |
| `docs/verification/M05_VERIFICATION.md` | M05 verification evidence and exact command results |
| `docs/handoffs/M05_HANDOFF.md` | M05 completion handoff for M06 |
| `docs/verification/M06_VERIFICATION.md` | M06 verification evidence and exact command results |
| `docs/handoffs/M06_HANDOFF.md` | M06 completion handoff for M07 |
| `milestones/M06.md` | Detailed M06 scope and completion requirements |

## Scope Boundaries

GridOps Intelligence does not control or dispatch the electricity grid, issue emergency or reliability declarations, provide electricity-trading recommendations, replace official system-operator forecasts, perform power-flow calculations, or make unsupported causal claims.
