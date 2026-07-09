# AGENTS.md — GridOps Intelligence

## Project Purpose

GridOps Intelligence is a production-style energy data engineering, forecasting, and MLOps platform focused on Ontario electricity demand.

The system will ingest public electricity and weather data, preserve raw source evidence, validate and normalize data, produce day-ahead hourly demand forecasts, quantify uncertainty, detect operational attention conditions, support planning scenarios, expose APIs, and provide an operational dashboard.

This is not a notebook project. Build it as a tested, reproducible, production-style decision-support system.

## Development Model

The project is built milestone by milestone.

Each milestone has its own file:

```text
milestones/M01.md
milestones/M02.md
milestones/M03.md
milestones/M04.md
milestones/M05.md
milestones/M06.md
milestones/M07.md

Before working on a milestone, read the active milestone file and follow its scope.

Do not start future milestone work early.

Required Files to Read First

Before making changes, read:

README.md
PROJECT_RULES.md
CURRENT_STATE.md
ROADMAP.md
ARCHITECTURE.md
DECISIONS.md
KNOWN_LIMITATIONS.md
the active milestone file in milestones/
the previous milestone handoff in docs/handoffs/, if present
the previous milestone verification report in docs/verification/, if present
Branching Rules

Do not work directly on main.

Use the active milestone branch:

m01
m02
m03
m04
m05
m06
m07

Before making changes, run:

git status
git branch --show-current

Do not mix unrelated milestone work into the active branch.

Approved High-Level Stack
Backend
Python 3.12
FastAPI
Pydantic
Pydantic Settings
SQLAlchemy 2.x
Alembic
PostgreSQL
HTTPX
Data Engineering
Prefect
dbt
Pandera or Great Expectations

Only introduce these when the active milestone requires them.

Machine Learning
scikit-learn
LightGBM or XGBoost
statsmodels
SHAP
MLflow

Do not introduce ML dependencies before the forecasting and MLOps milestones.

Frontend
Next.js
TypeScript
ECharts or Recharts

Do not introduce frontend work before the dashboard milestone.

Infrastructure and Testing
Docker Compose
GitHub Actions
Pytest
Ruff
MyPy
Engineering Rules

Prioritize:

correctness
reproducibility
explicit contracts
simple design
tested behavior
clear documentation
honest limitations

Avoid:

unnecessary abstraction
premature frameworks
unrelated rewrites
silent data loss
silent overwrites
fake production readiness
invented performance claims
Time Rules

Time handling is critical for this project.

Rules:

Use timezone-aware datetimes.
Store canonical operational timestamps in UTC.
Interpret Ontario local time using America/Toronto.
Do not silently accept naive datetimes.
Do not assume every Ontario local day has 24 hours.
Preserve source-native timestamps where relevant.
Preserve IESO source-native date and hour-ending fields.
Do not treat IESO hour-ending as a normal zero-based clock hour.
Handle daylight-saving transitions explicitly.

Any source timestamp ambiguity must be documented and tested.

Data Rules

For source data:

preserve raw evidence where required
store retrieval metadata
store publication metadata when available
store source URL or retrieval identifier
compute content hashes where relevant
preserve source-native fields
make ingestion idempotent
record failures safely
avoid duplicate facts
document revision behavior

Do not discard source evidence just because normalized tables are easier to use.

Testing Rules

Automated tests must be deterministic.

Do not depend on live internet in automated tests.

Use:

fixtures
mocks
temporary directories
isolated test databases
controlled sample payloads

Default quality commands:

uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest -q

If commands change, update documentation immediately.

Database and Migration Rules

Use PostgreSQL for integration behavior.

Do not silently replace PostgreSQL with SQLite where PostgreSQL behavior matters.

For migrations:

use Alembic
support clean-database upgrade
avoid premature future-domain tables
document migration commands
test upgrade behavior where practical
preserve migration history

Do not create tables for future milestones unless the active milestone requires them.

Documentation Rules

When code changes, update documentation in the same change set.

Keep these files accurate:

README.md
CURRENT_STATE.md
ROADMAP.md
ARCHITECTURE.md
DECISIONS.md
KNOWN_LIMITATIONS.md

At milestone completion, create or update:

docs/verification/MXX_VERIFICATION.md
docs/handoffs/MXX_HANDOFF.md

Documentation must distinguish between:

implemented behavior
planned behavior
assumptions
optional live smoke checks
known limitations
deferred work

Do not describe planned components as complete.

Security Rules

Do not commit:

secrets
API keys
passwords
private tokens
local .env files
downloaded raw data that should remain local
credentials in logs

Use .env.example for safe examples.

Never print sensitive values in logs, test output, or documentation.

Stop Conditions

Stop and ask for guidance instead of guessing if:

source behavior contradicts assumptions
data licensing is unclear
an API key appears required
IESO time behavior is uncertain
weather provider choice has long-term implications
a database schema decision affects future milestones
the requested change crosses milestone boundaries
a tool substitution changes the approved stack
the work requires a major redesign
tests cannot be made deterministic
CI requires a major platform change
Codex Response Format

Before implementation, report:

Repository state:
Current branch:
Files reviewed:
Understanding of active milestone:
Implementation plan:
Risks or uncertainties:

After implementation, report:

Files changed:
What was implemented:
Migrations added:
Commands run:
Exact results:
Tests added:
Known limitations:
Documentation updated:
Deferred work:
Completion gate status:

Do not claim completion without exact command results.

Project Non-Goals

GridOps Intelligence does not:

control the electricity grid
dispatch resources
issue emergency declarations
replace official IESO forecasts
provide trading recommendations
perform power-flow calculations
make unsupported causal claims

All public-facing claims must be supported by verified artifacts.

Final Rule

When uncertain, stop and ask.

Do not guess silently in areas involving time, source data, database design, data quality, model evaluation, or operational claims.