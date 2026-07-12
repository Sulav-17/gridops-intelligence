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

**Status:** Complete

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

M03-C01 implemented the quality schema, core contracts, and persistence helpers. M03-C02A implemented deterministic IESO hourly demand quality checks. M03-C02B implemented deterministic weather and source metadata checks. M03-C03 implemented blocking logic and source-health output. M03-C04 implemented the persisted quality runner, deterministic runner coverage, quality documentation, verification, and handoff artifacts.

## M04 - Baselines and Backtesting

**Status:** Complete and merged to `main`

**Owner:** Daniel Brooks, Senior Forecasting Scientist

**Objective:** Create point-in-time-correct feature snapshots and trusted forecasting evaluation.

Primary outcomes:

- forecast issuance contract
- as-of joins
- persisted feature snapshot foundation
- seasonal-naive baselines
- Ridge regression benchmark
- rolling or expanding evaluation
- slice metrics
- leakage tests
- reproducible evaluation reports

M04-C01 implemented the forecast issue contract, horizon generation, schema foundation, and lineage structures. M04-C02 implemented point-in-time feature snapshots, leakage-safe demand/calendar features, weather observation as-of joins, archived weather forecast issue-time joins, and quality blocking integration. M04-C03 implemented same-hour-yesterday, same-hour-last-week, seasonal hourly mean, and Ridge baselines, deterministic backtest windows, aggregate metrics, slice metrics, and persistence. M04-C04 implemented the simple forecasting runner, final documentation, verification, and handoff artifacts.

## M05 - Production Forecasting and MLOps

**Status:** Complete

**Owner:** Elena Rossi, Senior ML Platform Engineer

**Objective:** Train, select, register, serve, schedule, and monitor a production forecasting candidate.

Primary outcomes:

- sklearn candidate
- nullable quantile output schema with P50-only generation
- peak-demand and peak-hour forecasts
- ramp outputs
- model-selection gates
- local artifact persistence
- production runner command boundaries
- drift and performance monitoring foundations

M05-C01 implemented production forecasting and MLOps schema plus typed contracts. M05-C02 implemented local artifact persistence and model-selection gate logic. M05-C03 implemented deterministic sklearn candidate training from M04 feature snapshots. M05-C04 implemented selected-artifact forecast generation with P50, peak, ramp, and lineage outputs. M05-C05 implemented monitoring foundations, production runner boundaries, final documentation, verification, and handoff artifacts.

## M06 - Alerts, Scenarios, and Briefings

**Status:** Complete

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

M06 fast-track chunk 1 implemented deterministic alert contracts, fixed-threshold high-demand and ramp rules, previous-forecast deviation alerts, M03 source-health context alerts, combined context alerts, alert evidence persistence, duplicate-active alert prevention, and lifecycle history. M06 fast-track chunk 2 implemented deterministic demand-growth, weather-adjustment, and combined scenarios; scenario persistence; deterministic briefing facts; and backend scenario/briefing API outputs.

M06 fast-track chunk 3 implemented alert API endpoints, decision runner commands, final verification, and handoff documentation.

## M07 - Dashboard, Deployment, and Release

**Status:** Active

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

M07-C01 implemented the dashboard integration matrix, read-only overview/forecast/model-performance/system-status backend contracts, demo-mode restrictions, and server-side demo scenario bounds.

M07-C02 implemented the `frontend/` Next.js App Router foundation, a typed C01 API client, explicit fixture-backed demo fallback, and responsive Overview, Forecasts, Data Quality, Model Performance, System Status, and limitations documentation screens.

M07-C03 implements Alerts (including evidence and lifecycle detail), bounded Scenario simulations, and read-only persisted Briefing facts. The public UI has no alert evaluation, lifecycle mutation, briefing generation, ingestion, training, inference, or model-promotion controls. Scenarios use the configured public bounds of -10 to +10 percent load growth, -2,000 to +2,000 MW added load, -10 to +10 C temperature, and -30 to +30 percent humidity; they remain simulations, weather adjustment remains deterministic, and humidity may not affect values. C03 frontend interaction tests cover these constraints and safe server errors. C04 deployment and release work remains deferred.
