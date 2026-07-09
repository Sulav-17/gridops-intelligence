# GridOps Intelligence Roadmap

## Status Legend

- Not started
- Active
- Complete
- Blocked

## M01 - Domain Contract and Foundation

**Status:** Complete

**Owner:** Ethan Cole, Senior Platform Engineer

**Objective:** Establish a reproducible repository, backend API, database foundation, CI pipeline, logging, and explicit time-domain rules.

Primary outcomes:

- Python project foundation
- FastAPI health and readiness endpoints
- PostgreSQL and SQLAlchemy
- Alembic migrations
- Docker Compose
- configuration and logging
- Ruff, MyPy, Pytest, and GitHub Actions
- UTC, Toronto time, DST, and IESO hour-ending contracts

## M02 - Data Ingestion and Normalized Storage

**Status:** Complete

**Owner:** Maya Chen, Senior Data Engineer

**Objective:** Acquire, archive, normalize, and track core electricity and weather data.

Primary outcomes:

- immutable raw snapshots
- source metadata and hashes
- fixture-backed IESO demand ingestion
- fixture-backed weather observations
- fixture-backed archived weather forecasts
- source revision handling
- ingestion observability through persisted ingestion runs
- idempotent and recoverable fixture workflows

M02 completion is fixture-backed. Live source clients, orchestration, and formal data quality remain deferred.

## M03 - Data Quality and Observability

**Status:** Active

**Owner:** Priya Shah, Senior Data Reliability Engineer

**Objective:** Prevent malformed, incomplete, duplicated, stale, or discontinuous source data from contaminating downstream datasets.

Primary outcomes:

- data contracts
- quality severities
- schema, range, completeness, uniqueness, freshness, and continuity checks
- DST validation
- persisted quality results
- source-health service or report
- downstream blocking rules

M03-C01 has implemented the quality schema, core contracts, and persistence helpers. M03-C02A has implemented deterministic IESO hourly demand quality checks. M03-C02B has implemented deterministic weather and source metadata checks. M03-C03 has implemented blocking logic and source-health output. Runner commands and milestone handoff/verification remain in progress.

## M04 - Baselines and Backtesting

**Status:** Not started

**Owner:** Daniel Brooks, Senior Forecasting Scientist

**Objective:** Create point-in-time-correct feature snapshots and trusted forecasting evaluation.

Primary outcomes:

- forecast issuance contract
- as-of joins
- gold feature tables
- seasonal-naive baselines
- Ridge regression benchmark
- rolling or expanding evaluation
- slice metrics
- leakage tests
- reproducible evaluation reports

## M05 - Production Forecasting and MLOps

**Status:** Not started

**Owner:** Elena Rossi, Senior ML Platform Engineer

**Objective:** Train, select, register, serve, schedule, and monitor a production forecasting candidate.

Primary outcomes:

- LightGBM or XGBoost candidate
- quantile forecasting
- P10, P50, and P90 outputs
- peak-demand and peak-hour forecasts
- ramp outputs
- MLflow experiment tracking and registry
- model-selection gates
- scheduled inference
- forecast API
- drift and performance monitoring

## M06 - Alerts, Scenarios, and Briefings

**Status:** Not started

**Owner:** Marcus Lee, Senior Decision Systems Engineer

**Objective:** Turn forecasts and source-health information into transparent operational attention signals.

Primary outcomes:

- high-demand alerts
- ramp alerts
- deviation alerts
- source-health alerts
- combined contextual alerts
- alert lifecycle
- controlled scenario engine
- deterministic briefing facts
- optional guarded narrative generation

## M07 - Dashboard, Deployment, and Release

**Status:** Not started

**Owner:** Olivia Grant, Senior Product and Deployment Engineer

**Objective:** Deliver the complete public-facing product and verified portfolio release.

Primary outcomes:

- Next.js operational dashboard
- forecast and uncertainty screens
- alert and source-health screens
- scenario interface
- model-performance views
- public read-only demo
- production deployment
- documentation
- architecture diagrams
- case study
- demo video
- verified `v1.0.0` release
