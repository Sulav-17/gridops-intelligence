# Current State

## Project

GridOps Intelligence

## Current Phase

M03-C02B weather and source metadata quality checks implemented

## Active Milestone

M03 - Data Quality and Observability

## Milestone Owner

Priya Shah - Senior Data Reliability Engineer

## Project Leader

Samantha

## Repository Status

M01 is complete.

M02 is complete and merged to `main`.

The active milestone is M03 on branch `m03`.

M03-C01 has implemented the quality schema and core contracts. M03-C02A has implemented
generic in-memory quality check result utilities and deterministic IESO hourly demand checks.
M03-C02B has implemented deterministic weather dataset and source metadata checks.
Blocking logic, source-health output, and a quality runner have not been implemented yet.

Implemented storage that already exists:

- ingestion run tracking
- raw snapshot metadata persistence
- local immutable raw payload storage by source and SHA-256 hash
- source registry contract
- IESO hourly demand fixture parser and loader
- weather observation fixture parser and loader
- archived weather forecast fixture parser and loader
- normalized silver tables for the three M02 sources
- idempotent loading
- simple changed-record revision evidence
- simple fixture ingestion runner
- deterministic parser, loader, storage, runner, and migration tests
- source contract, runbook, verification, and handoff documentation

No future milestone features have been implemented.

## Technical State

- Python version: 3.12
- package: `gridops`
- database: PostgreSQL
- local database port: `55432`
- migrations: empty baseline plus M02 ingestion storage migration
- API: FastAPI health and readiness only
- ingestion: fixture mode only through `python -m gridops.ingestion.runner`
- tests: unit and PostgreSQL integration coverage for M01 and M02 behavior

## Implemented Data Storage

Bronze tables:

- `ingestion_runs`
- `raw_snapshots`

Silver tables:

- `ieso_hourly_demand`
- `weather_observations`
- `weather_forecasts`

These implemented storage tables preserve raw snapshot references, ingestion run references, source-native fields, normalized UTC timestamps, row hashes, current-state flags, and superseded timestamps.

Quality tables:

- `quality_runs`
- `quality_results`

Quality storage records run lifecycle state and individual quality result metadata for existing M02 datasets without storing raw payloads or secrets.

## Implemented Quality Checks

IESO hourly demand:

- required-column schema checks
- required-field nullability checks
- duplicate current source-native key checks
- conservative demand range checks
- UTC timestamp ordering and one-hour duration checks
- hourly UTC interval continuity checks
- source-hour completeness checks
- fixed-clock freshness checks
- DST alignment checks using M01 time utilities where the M02 schema can represent the source-native hour

Weather observations:

- required-column schema checks
- required-field nullability checks
- duplicate current source key checks
- conservative weather value range checks
- UTC timestamp checks
- fixture-supported hourly continuity checks
- fixed-clock freshness checks

Weather forecasts:

- required-column schema checks
- required-field nullability checks
- duplicate current forecast key checks
- broad provider-neutral value range checks
- UTC issue/valid timestamp and lead-time checks
- fixture-supported valid-time completeness checks
- fixed-clock freshness checks

Source metadata:

- raw snapshot required metadata checks
- ingestion run lifecycle, timestamp, count, and safe failure-detail checks

## Not Implemented Yet

- M03 blocking logic
- M03 source-health API or operational report
- M03 quality runner
- live source fetching
- IESO API clients
- weather provider API clients
- dbt
- Prefect
- MLflow
- forecasting models
- backtesting
- gold feature tables
- alerts
- scenarios
- frontend or dashboards
- authentication
- production deployment

## Verification Evidence

Final M02 verification is recorded in `docs/verification/M02_VERIFICATION.md`.

## Immediate Next Action

Begin M03-C03 blocking logic and source-health output.
