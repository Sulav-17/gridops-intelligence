# GridOps Intelligence Architecture

## Document Status

This document distinguishes between:

- approved target architecture
- architecture actually implemented

Do not describe planned components as complete.

## Current Implemented Architecture

No application architecture has been implemented yet.

The repository currently contains only project-governance and milestone-planning documents.

## Approved Target Architecture

The planned system flow is:

1. IESO, weather, and calendar sources
2. ingestion workflows
3. immutable raw snapshots
4. validation, normalization, and revision handling
5. PostgreSQL warehouse
6. dbt transformations where useful
7. point-in-time feature snapshots
8. leakage-safe backtesting
9. MLflow experiment tracking and model registry
10. scheduled inference
11. forecast, quality, alert, scenario, and briefing services
12. FastAPI backend
13. Next.js operational dashboard

## Planned Data Layers

### Bronze

Preserves source evidence:

- original source files or payloads
- source URL
- publication time
- retrieval time
- file hash
- parser version
- ingestion-run identifier

### Silver

Normalizes source data while retaining source meaning:

- UTC timestamp
- Ontario local-time interpretation
- source-native date and time fields
- IESO hour-ending values
- normalized units
- revision metadata
- quality flags

### Gold

Supports operational and analytical use:

- hourly demand facts
- weather features
- model feature snapshots
- forecasts
- prediction intervals
- evaluation metrics
- alerts
- scenario results
- briefing facts

## M01 Architectural Boundary

M01 may establish:

- Python package structure
- FastAPI application structure
- configuration
- structured logging
- PostgreSQL connectivity
- SQLAlchemy foundation
- Alembic
- Docker Compose
- health and readiness behavior
- CI
- time-domain utilities and contracts

M01 must not implement:

- real IESO ingestion
- weather ingestion
- Prefect flows
- dbt models
- training datasets
- forecasting models
- MLflow
- alert logic
- scenario logic
- frontend features

## Time Architecture

Approved principles:

- canonical operational storage uses timezone-aware UTC timestamps
- Ontario local-time interpretation uses `America/Toronto`
- naive datetimes must not be accepted silently
- IESO hour-ending fields must be preserved
- daylight-saving ambiguity must be handled explicitly
- source publication and retrieval times must remain distinguishable
- no implementation may assume that every Ontario local day contains 24 hours

Detailed implementation will be established and tested during M01.