# GridOps Intelligence

GridOps Intelligence is a production-style energy data engineering, forecasting, and MLOps platform focused on Ontario electricity demand.

The system is intended to:

- ingest public electricity and weather data
- preserve immutable source snapshots and metadata
- validate and normalize changing source data
- produce day-ahead hourly demand forecasts
- quantify forecast uncertainty
- detect operational attention conditions
- support controlled planning scenarios
- expose results through APIs and an operational dashboard

M02 is now the implemented ingestion foundation. Forecasting, alerts, scenarios, dashboards, authentication, deployment, dbt, Prefect, and MLflow are intentionally not implemented yet.

## Current Status

The repository has completed M02 - Data Ingestion Foundation.

Implemented foundation:

- Python 3.12 src-based package managed by uv
- Ruff formatting and linting
- strict MyPy
- Pytest
- typed `GRIDOPS_` configuration with secret-aware database URL handling
- structured JSON logging with UTC timestamps and defensive redaction
- synchronous SQLAlchemy database foundation
- empty Alembic baseline
- Docker Compose PostgreSQL on host port 55432
- FastAPI app factory with `/health` and `/ready`
- UTC, `America/Toronto`, DST, and IESO hour-ending utilities
- GitHub Actions CI quality gates
- ingestion run tracking
- immutable raw snapshot metadata and local raw file storage
- SHA-256 payload and row hashing
- fixture-backed IESO hourly demand ingestion
- fixture-backed weather observation ingestion
- fixture-backed archived weather forecast ingestion
- idempotent silver loaders with simple revision evidence

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

Verify the package import:

```powershell
uv run python -c "import gridops; print(gridops.__name__, gridops.__version__)"
```

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

Run fixture ingestion:

```powershell
$env:GRIDOPS_DATABASE_URL = "postgresql+psycopg://gridops:gridops@127.0.0.1:55432/gridops_test"
uv run alembic upgrade head
uv run python -m gridops.ingestion.runner --source ieso-demand --mode fixture --path tests/fixtures/ingestion/ieso/hourly_demand_sample.csv
uv run python -m gridops.ingestion.runner --source weather-observations --mode fixture --path tests/fixtures/ingestion/weather/observations_sample.csv
uv run python -m gridops.ingestion.runner --source weather-forecasts --mode fixture --path tests/fixtures/ingestion/weather/forecasts_sample.csv
Remove-Item Env:\GRIDOPS_DATABASE_URL
```

## Configuration

Application settings are defined in `gridops.config.Settings` using Pydantic Settings. Settings can be supplied through environment variables or a local `.env` file. Every supported environment variable uses the `GRIDOPS_` prefix.

Supported settings:

- `GRIDOPS_APP_NAME`
- `GRIDOPS_APP_ENVIRONMENT`
- `GRIDOPS_LOG_LEVEL`
- `GRIDOPS_API_HOST`
- `GRIDOPS_API_PORT`
- `GRIDOPS_DATABASE_URL`
- `GRIDOPS_READINESS_TIMEOUT_SECONDS`

Copy `.env.example` to `.env` for local development:

```powershell
Copy-Item .env.example .env
```

## API Foundation

Create the FastAPI app with:

```python
from gridops.api import create_app

app = create_app()
```

Endpoints:

- `GET /health` returns process health and does not touch the database.
- `GET /ready` checks real PostgreSQL connectivity and returns a safe `503` response when the dependency is unavailable.

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
| `milestones/M02.md` | Detailed M02 scope and completion requirements |

## Scope Boundaries

GridOps Intelligence does not control or dispatch the electricity grid, issue emergency or reliability declarations, provide electricity-trading recommendations, replace official system-operator forecasts, perform power-flow calculations, or make unsupported causal claims.
