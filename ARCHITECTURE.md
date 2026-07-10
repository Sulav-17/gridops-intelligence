# GridOps Intelligence Architecture

## Document Status

This document distinguishes between approved target architecture and architecture actually implemented. Planned components are not described as complete until they exist in the repository.

## Current Implemented Architecture

M01 through M05 are implemented and complete. M06 is active on branch `m06`, owned by Marcus Lee, Senior Decision Systems Engineer.

### Foundation

- Python 3.12 project using a `src` layout
- uv dependency management and lockfile
- Ruff, MyPy, and Pytest
- typed Pydantic Settings with `GRIDOPS_` prefix
- structured JSON logging with UTC timestamps and secret redaction
- synchronous SQLAlchemy engine and session helpers
- PostgreSQL as the primary relational database
- Alembic migrations
- Docker Compose PostgreSQL on host port `55432`
- FastAPI app factory with `/health`, `/ready`, and `GET /quality/health`
- explicit UTC, Toronto time, DST, and IESO hour-ending utilities

### M02 Ingestion Foundation

Bronze storage:

- `ingestion_runs`
- `raw_snapshots`
- local raw payload files stored by source and SHA-256 hash

Silver storage:

- `ieso_hourly_demand`
- `weather_observations`
- `weather_forecasts`

Ingestion code:

- source registry contract
- SHA-256 hashing utility
- raw snapshot storage abstraction
- fixture-backed IESO hourly demand parser and loader
- fixture-backed weather observation parser and loader
- fixture-backed archived weather forecast parser and loader
- simple fixture runner through `python -m gridops.ingestion.runner`

Silver rows retain raw snapshot IDs, ingestion run IDs, source-native fields, normalized UTC timestamps, row hashes, `is_current`, and `superseded_at_utc`.

### M03 Quality Layer

Quality storage:

- `quality_runs`
- `quality_results`

Quality contracts and persistence:

- typed quality severity, run status, result status, and check category contracts
- dataset quality contract definitions for existing M02 storage tables
- persistence helpers for quality runs and quality results
- generic in-memory quality check result utilities compatible with quality result persistence

Implemented dataset checks:

- deterministic IESO hourly demand schema, nullability, uniqueness, range, timestamp, continuity, completeness, freshness, and DST alignment checks
- deterministic weather observation schema, nullability, uniqueness, range, timestamp, fixture-supported continuity, and freshness checks
- deterministic weather forecast schema, nullability, uniqueness, range, timestamp, fixture-supported valid-time completeness, and freshness checks
- deterministic raw snapshot and ingestion run source metadata checks

Implemented quality services:

- persisted blocking decisions over quality runs and results
- dataset source-health summaries built from latest persisted quality runs and results
- FastAPI `GET /quality/health` endpoint for safe operational visibility
- simple persisted quality runner through `python -m gridops.quality.runner`

The quality layer does not auto-run checks from ingestion, implement an alert lifecycle, or introduce orchestration.

### M04 Forecasting Evaluation Foundation

Forecasting storage:

- `forecast_issues`
- `feature_snapshot_runs`
- `feature_snapshot_rows`
- `baseline_forecast_runs`
- `baseline_forecast_predictions`
- `baseline_metric_results`
- `baseline_slice_metric_results`

Forecasting contracts and feature logic:

- UTC-only forecast issue contract with deterministic horizon generation
- next-N hourly target interval generation
- point-in-time feature snapshot rows
- leakage-safe demand lag, rolling, recent ramp, and calendar features
- weather observation as-of joins using `observed_at_utc <= forecast_issue_time_utc`
- archived weather forecast as-of joins using `issue_time_utc <= forecast_issue_time_utc`
- M03 quality-blocking decisions applied before trusted feature rows are persisted

Baseline evaluation:

- same-hour-yesterday baseline
- same-hour-last-week baseline
- seasonal hourly mean baseline
- simple deterministic Ridge baseline using scikit-learn
- rolling and expanding backtest window definitions
- final untouched test-period reservation in backtest configuration
- MAE, RMSE, WAPE, and bias metrics
- slice metrics by lead hour, target hour, day of week, weekend flag, month, and season
- persisted baseline run, prediction, aggregate metric, and slice metric rows

Runner:

- simple standard-library runner through `python -m gridops.forecasting.runner`
- deterministic dry-run previews for feature building, backtest windows, and reports

M04 is an evaluation foundation, not a production forecasting service.

### M05 Production Forecasting And MLOps Schema

M05-C01 adds schema and typed contracts. M05-C02 adds local artifact persistence utilities and model-selection gate logic. M05-C03 adds deterministic sklearn candidate training from persisted M04 feature snapshots. M05-C04 adds production forecast generation from selected local model artifacts. M05-C05 adds minimal performance and drift monitoring summaries plus simple production runner command boundaries. The repository still does not register models in MLflow, schedule inference, or expose forecast APIs.

M05 storage:

- `model_training_runs`
- `model_artifacts`
- `model_selection_results`
- `production_forecast_runs`
- `production_forecast_predictions`
- `forecast_peak_outputs`
- `forecast_ramp_outputs`
- `model_performance_summaries`
- `model_drift_summaries`

Implemented contract surfaces include model training status, artifact status, selection status, forecast run status, forecast prediction rows with nullable P10/P90 and required P50 or point forecast, peak output rows, ramp output rows, performance summaries, and drift summaries.

Artifact persistence writes local pickle artifacts under an ignored artifact directory, computes SHA-256 hashes from file bytes, loads local artifacts back, and persists model artifact metadata to `model_artifacts`.

Model selection compares candidate metrics to a selected M04 baseline. The default gate requires candidate MAE to be no worse than baseline MAE, candidate WAPE to be no worse when both sides provide WAPE, complete lineage fields, and no slice sanity failures. Passing and failing decisions can be persisted to `model_selection_results`.

Candidate training reads features only from `feature_snapshot_rows.lineage_metadata` and uses `ieso_hourly_demand` only as the supervised label source. It uses time-based training and evaluation windows, rejects random splits, persists `model_training_runs`, saves a local model artifact, persists `model_artifacts`, calculates MAE, RMSE, WAPE, and bias, and persists the model-selection result.

Forecast generation loads a selected available artifact, reuses or builds M04 feature snapshots for a supplied issue time, extracts the same approved feature vector, persists `production_forecast_runs`, stores P50-only prediction rows with nullable P10/P90 fields, and derives peak and ramp output rows. Forecast run and prediction lineage preserve artifact, training run, feature snapshot run, feature version, and issue-time references.

Monitoring foundations calculate forecast-vs-actual MAE, RMSE, WAPE, and bias where actuals are available, and persist simple feature mean-difference drift summaries. No alerting, notifications, dashboard, model registry, or production scheduler is implemented.

Runner:

- simple standard-library runner through `python -m gridops.forecasting.production_runner`
- deterministic dry-run previews for candidate training, forecast generation, and monitoring summaries
- database-backed execution paths for already implemented training, forecast generation, and monitoring helpers

### M06 Alert Foundation

M06 fast-track chunk 1 adds deterministic alert contracts, rule evaluation, evidence persistence, duplicate-active alert prevention, and lifecycle history. Chunk 2 adds scenario analysis, deterministic briefing facts, and backend API outputs. Runner commands and M07 dashboard presentation remain deferred.

M06 alert storage:

- `alert_evaluation_runs`
- `alerts`
- `alert_evidence`
- `alert_lifecycle_history`

Implemented alert behavior:

- fixed-threshold high-demand alerts from M05 production forecast predictions
- large-ramp alerts using M05 `forecast_ramp_outputs` when present, with deterministic adjacent-prediction fallback
- forecast deviation alerts compared against the previous succeeded production forecast run for the same target interval
- source-health context alerts from persisted M03 quality/source-health summaries
- combined-context alerts from deterministic forecast attention plus source-health component signals
- deterministic SHA-256 business fingerprints excluding database IDs, random values, and processing timestamps
- partial unique database protection against duplicate active alerts for the same fingerprint
- lifecycle transitions from open to acknowledged, resolved, suppressed, or expired, and from acknowledged to resolved, suppressed, or expired
- immutable evidence and lifecycle history rows

True uncertainty/confidence alerting remains deferred because M05 stores nullable P10/P90 columns but does not generate true prediction intervals or confidence indicators.

### M06 Scenario And Briefing Foundation

M06 fast-track chunk 2 adds controlled scenario analysis and deterministic briefing facts. Scenario outputs are persisted simulations, not forecasts. Briefing facts are structured records with evidence references, not generated narrative.

M06 scenario and briefing storage:

- `scenario_runs`
- `scenario_assumptions`
- `scenario_result_rows`
- `briefing_runs`
- `briefing_facts`

Implemented scenario behavior:

- demand-growth scenarios apply percent growth and added MW assumptions to M05 base forecast values
- weather-adjustment scenarios apply a documented deterministic approximation of `75.000 MW` per degree C because M05 cannot safely recompute forecasts from changed weather features
- combined weather/load scenarios add the deterministic demand and weather deltas
- scenario assumptions, limitations, interval results, and peak summaries are persisted

Implemented briefing behavior:

- deterministic fact generation from production forecast runs, predictions, peak outputs, ramp outputs, alerts, source-health summaries, scenarios, and known limitations
- facts include forecast issue/horizon, expected peak, largest ramp, open alert summary, highest attention hours, source-health summary, quality limitations, confidence limitations, scenario highlights, and unsupported claims
- no LLM or free-form narrative generation

API outputs:

- `POST /scenarios`
- `GET /scenarios/{scenario_id}`
- `POST /briefings/generate`
- `GET /briefings/latest`

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

## Current Boundaries

The current repository does not implement live source fetching, Prefect orchestration, dbt transformations, MLflow, scheduled production inference, forecast APIs, dashboard work, authentication, or deployment. Alert APIs, runner commands, notifications, and ticketing are not implemented.
