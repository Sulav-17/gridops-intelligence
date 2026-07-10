# GridOps Intelligence

GridOps Intelligence is a production-style energy data engineering, forecasting, and MLOps platform focused on Ontario electricity demand.

The system is intended to ingest public electricity and weather data, preserve source evidence, validate and normalize changing source data, produce trusted day-ahead forecasting evaluations, and support production forecasting, alerts, scenarios, APIs, and an operational dashboard.

M06 is active on branch `m06`. M01 through M05 are complete.

## Current Status

Completed milestones:

- M01 - Foundation and environment readiness
- M02 - Data ingestion foundation
- M03 - Data quality and observability
- M04 - Baselines and backtesting

Active milestone:

- M06 - Alerts, Scenarios, and Briefings, owned by Marcus Lee, Senior Decision Systems Engineer

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

Not implemented yet:

- live source fetching
- orchestration with Prefect
- dbt transformations
- production forecast API or model serving
- true quantile models or prediction intervals
- MLflow registry
- scheduled inference
- dashboards, authentication, or deployment

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

No production forecast API exists yet.

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
| `milestones/M05.md` | Detailed M05 scope and completion requirements |

## Scope Boundaries

GridOps Intelligence does not control or dispatch the electricity grid, issue emergency or reliability declarations, provide electricity-trading recommendations, replace official system-operator forecasts, perform power-flow calculations, or make unsupported causal claims.
