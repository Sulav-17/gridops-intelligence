# GridOps Intelligence Case Study

## Problem and users

Ontario demand operations need a trustworthy way to connect source evidence, data quality, forecast evaluation, and decision-support context. GridOps Intelligence is a portfolio-grade reference product for analysts, data engineers, forecast engineers, and operations stakeholders who need to inspect those layers without treating an application as a grid-control tool.

## Product goal

The product demonstrates an auditable path from fixture-backed source records to a decision-support dashboard. It prioritizes explicit contracts, reproducibility, time handling, and limitation visibility over unsupported automation claims.

## Architecture and ingestion

Python services ingest fixture-based IESO demand, weather observation, and archived weather forecast data into PostgreSQL. Raw snapshots, hashes, retrieval metadata, source-native fields, normalized UTC timestamps, and revision state preserve evidence. The system keeps Ontario interpretation explicit through `America/Toronto` and source-native IESO hour-ending fields.

## Quality, forecasting, and MLOps foundation

Persisted quality runs provide source-health summaries and blocking decisions. Leakage-aware feature snapshots support same-hour baselines and a simple Ridge baseline, rolling or expanding backtest windows, and persisted MAE, RMSE, WAPE, bias, and slice metrics. The MLOps foundation persists model training metadata, local artifact hashes, selection gates, production forecast outputs, peaks, ramps, performance summaries, and feature-drift summaries.

P10/P90 are nullable fields, not a claim that genuine prediction intervals exist. No forecast-superiority claim is made without persisted evidence.

## Operational decision support

Deterministic rule outputs produce alert records with immutable evidence and lifecycle history. Bounded scenarios compare source forecast intervals with deterministic simulations; they do not retrain a model or replace production forecasts. Briefings are structured persisted facts rather than generated narrative. The dashboard presents each layer with source, limitation, loading, empty, and unavailable states.

## Testing and release practice

The repository uses Ruff, MyPy, Pytest, Alembic, frontend linting/typechecking/tests/build, API smoke checks, and documented manual dashboard review. The container runs FastAPI as a non-root user. CORS is configurable, demo-mode mutations are blocked, and a manual secret review is part of release readiness.

## Deployment and limitations

The intended deployment is a Vercel-compatible frontend, containerized FastAPI backend, and managed PostgreSQL. No hosted deployment or live ingestion is asserted. The product does not dispatch grid resources, declare emergencies, offer trading guidance, or provide protected multi-user operations.

## Professional skills demonstrated

This work demonstrates data-contract design, PostgreSQL/Alembic engineering, time-series evaluation, typed API design, UI integration, MLOps foundations, security-conscious configuration, reproducible testing, release documentation, and evidence-based technical communication.
