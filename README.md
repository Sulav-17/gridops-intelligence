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

## Project Positioning

GridOps Intelligence is designed as a portfolio-grade operational decision system rather than a standalone notebook.

Approximate project balance:

- 65% data engineering
- 35% machine learning

Primary role alignment:

- Data Engineer
- Analytics Engineer
- ML Engineer
- Energy Data Analyst
- Applied AI Engineer

## Current Status

The repository is currently in:

**M01 — Domain Contract and Foundation**

See:

- `CURRENT_STATE.md`
- `ROADMAP.md`
- `milestones/M01-foundation.md`
- `PROJECT_RULES.md`

## Planned Technology Stack

### Backend

- Python 3.12
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- PostgreSQL
- HTTPX

### Data Engineering

- Prefect
- dbt
- Pandera or Great Expectations

### Machine Learning

- scikit-learn
- LightGBM or XGBoost
- statsmodels
- SHAP
- MLflow

### Frontend

- Next.js
- TypeScript
- ECharts or Recharts

### Infrastructure and Testing

- Docker Compose
- GitHub Actions
- Pytest
- Ruff
- MyPy

Only the tools needed for the active milestone should be introduced.

## Development Model

The project is developed using:

- one milestone per ChatGPT thread
- one milestone branch at a time
- small implementation tickets
- verification before ticket approval
- repository-based handoffs between milestones
- Samantha as Project Leader and final architectural authority

## Project Documents

| Document | Purpose |
|---|---|
| `PROJECT_RULES.md` | Permanent project execution rules |
| `CURRENT_STATE.md` | Current verified repository status |
| `ROADMAP.md` | Seven-milestone delivery plan |
| `ARCHITECTURE.md` | Architecture actually implemented or formally approved |
| `DECISIONS.md` | Important architectural and project decisions |
| `KNOWN_LIMITATIONS.md` | Honest limitations and deferred work |
| `milestones/M01-foundation.md` | Detailed scope and completion requirements for M01 |
| `docs/handoffs/` | Milestone handoff documents |
| `docs/verification/` | Reproducible verification reports |

## Important Scope Boundaries

GridOps Intelligence does not:

- control or dispatch the electricity grid
- issue emergency or reliability declarations
- provide electricity-trading recommendations
- replace official system-operator forecasts
- perform power-flow calculations
- make unsupported causal claims

## Local Development

### Requirements

- Git
- uv
- Python 3.12

### Install dependencies

```powershell
uv sync --all-groups
```

### Verify the package import

```powershell
uv run python -c "import gridops; print(gridops.__name__, gridops.__version__)"
```

### Run quality checks

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest -q
```

The Python version is pinned through `.python-version`, and dependencies are locked in `uv.lock`.


## Configuration

Application settings are defined in `gridops.config.Settings` using Pydantic Settings.

Settings can be supplied through environment variables or a local `.env` file. Every supported environment variable uses the `GRIDOPS_` prefix.

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

The database URL is handled as a secret value and must use a PostgreSQL scheme. Real credentials must never be committed.

## Structured Logging

GridOps uses Python standard-library logging with a project JSON formatter.

Each application log record includes:

- UTC timestamp
- severity level
- logger name
- message
- explicitly supplied structured context

Recognized credential fields and common credentials embedded in text are redacted before output. Logging currently writes to standard output and does not depend on an external logging service.