# Known Limitations

## Current Repository

The repository contains the completed M01 foundation, M02 ingestion foundation, M03 data quality and observability milestone, M04 forecasting evaluation foundation, M05 production forecasting and MLOps milestone, and M06 alert, scenario, and briefing milestone.

Implemented M02 ingestion is fixture-backed only:

- IESO hourly demand CSV fixtures
- weather observation CSV fixtures
- archived weather forecast CSV fixtures
- raw snapshot metadata and local raw file storage
- ingestion run tracking
- idempotent silver loaders
- simple changed-record revision evidence

Implemented M03-C01 quality foundation includes:

- quality severity, run status, result status, and check category enums
- dataset quality contracts for existing M02 tables
- quality run and quality result tables
- persistence helpers for quality runs and quality results

Implemented M03-C02A quality checks include deterministic IESO hourly demand:

- schema and required-field checks
- duplicate current source-native key checks
- conservative demand range checks
- timestamp, continuity, completeness, freshness, and DST alignment checks

Implemented M03-C02B quality checks include deterministic:

- weather observation schema, nullability, uniqueness, range, timestamp, fixture-supported continuity, and freshness checks
- weather forecast schema, nullability, uniqueness, range, timestamp, fixture-supported valid-time completeness, and freshness checks
- raw snapshot and ingestion run source metadata checks

Implemented M03 quality services include:

- persisted blocking decisions based on latest applicable quality runs and results
- safe source-health summaries for supported datasets
- `GET /quality/health` operational visibility endpoint
- `python -m gridops.quality.runner` persisted quality execution for supported datasets

Implemented M04 forecasting evaluation includes:

- forecast issue contract and deterministic hourly horizon generation
- M04 forecasting and baseline evaluation tables
- point-in-time feature snapshots with demand, calendar, weather observation, and archived forecast as-of logic
- M03 quality-blocking integration for trusted feature generation
- same-hour-yesterday, same-hour-last-week, seasonal hourly mean, and simple Ridge baselines
- rolling and expanding backtest window definitions
- MAE, RMSE, WAPE, bias, and slice metrics
- simple forecasting runner previews through `python -m gridops.forecasting.runner`

Implemented M05-C01 schema and contracts include:

- model training run metadata tables and typed status contracts
- model artifact metadata tables and typed status contracts
- model-selection result storage with candidate and baseline metrics JSON
- production forecast run and prediction tables
- nullable P10/P90 prediction fields with required P50 or point forecast support
- peak-demand and peak-hour output tables
- ramp output tables
- model performance and drift summary tables

Implemented M05-C02 artifact and selection foundations include:

- local artifact save/load utilities under ignored artifact paths
- deterministic SHA-256 artifact hashing from file bytes
- model artifact metadata persistence
- model-selection gate checks for MAE, WAPE, lineage completeness, and slice sanity failures
- persisted selected or rejected gate decisions with reasons

Implemented M05-C03 candidate training includes:

- deterministic sklearn gradient boosting candidate training
- time-based training and evaluation windows only
- M04 `feature_snapshot_rows` as the only feature source
- IESO demand actuals used only as supervised labels
- persisted model training run lifecycle
- artifact save and metadata persistence
- MAE, RMSE, WAPE, and bias calculation
- comparison against persisted M04 baseline metrics through the model-selection gate

Implemented M05-C04 forecast generation includes:

- selected available artifact validation
- M04 feature snapshot reuse or build behavior for a supplied issue time
- P50-only prediction persistence with nullable P10/P90 fields
- production forecast run persistence
- peak-demand and peak-hour output persistence
- ramp output persistence
- artifact, training run, feature snapshot, feature version, and issue-time lineage
- safe blocked-run behavior for unusable artifacts or feature snapshots

Implemented M05-C05 monitoring and runner foundations include:

- forecast-vs-actual MAE, RMSE, WAPE, and bias summaries where actuals are available
- simple deterministic feature mean-difference drift summaries
- explicit no-data drift summary behavior
- persisted `model_performance_summaries` and `model_drift_summaries`
- simple production runner command boundaries for training, forecast generation, and monitoring
- final M05 runbooks, forecast output contract, verification report, and handoff report

Implemented M06 alert foundation includes:

- alert type, severity, lifecycle, and evaluation status contracts
- high-demand alerts from M05 production forecast predictions
- ramp alerts using M05 ramp outputs where available, with deterministic adjacent-prediction fallback
- forecast deviation alerts against the previous succeeded production forecast run
- source-health context alerts from M03 persisted quality/source-health summaries
- combined-context alerts from deterministic component signals
- deterministic business fingerprints and duplicate-active alert prevention
- persisted alert evaluation runs, alert records, immutable evidence rows, and lifecycle history
- backend endpoints for alert listing, detail, evaluation, and lifecycle transitions
- alert rules documentation in `docs/decision/ALERT_RULES.md`

Implemented M06 scenario and briefing foundation includes:

- demand-growth scenarios with percent and added-MW assumptions
- weather-adjustment scenarios with a documented deterministic approximate temperature delta
- combined weather/load scenarios
- persisted scenario runs, assumptions, limitations, result rows, and summaries
- deterministic briefing facts from forecasts, peaks, ramps, alerts, source health, scenarios, and known limitations
- persisted briefing runs and briefing facts with evidence references
- backend endpoints for scenario generation, scenario lookup, briefing generation, and latest briefing lookup
- standard-library decision runner commands for alert evaluation, scenario runs, and briefing generation
- scenario and briefing runbooks in `docs/decision/`

## Missing Capabilities

The following are intentionally not implemented yet:

- live IESO source clients
- live weather provider clients
- scheduled ingestion
- Prefect orchestration
- dbt transformations
- MLflow tracking
- LightGBM or XGBoost production candidate
- true quantile forecasts or prediction intervals
- scheduled production inference
- production forecast API
- uncertainty or confidence alerts
- alert notifications or ticketing
- alert, scenario, and briefing dashboard screens
- authentication or authorization
- production deployment

## Ingestion Limitations

- The runner supports only `--mode fixture`.
- Raw payload files are local development artifacts under `data/raw` by default.
- Weather provider selection is deferred; weather fixtures use provider-neutral columns.
- Weather continuity and completeness checks are limited to caller-provided fixture assumptions until live provider contracts are selected.
- Weather forecast value range checks use broad provider-neutral bounds, not official provider-specific operational limits.
- Weather timestamps must include timezone information.
- Archived weather forecast lead time is derived only for whole-hour issue-to-valid differences.
- Revision behavior is simple current/superseded state, not a full bitemporal model.
- Failed runs store bounded sanitized error text, not full stack traces.

## Forecasting Evaluation Limitations

- Feature payloads are stored as structured JSON in `feature_snapshot_rows.lineage_metadata`; there is not yet a dedicated typed feature-store table.
- M04 operates on fixture-backed and locally seeded data; live data acquisition remains deferred.
- Ridge is a simple transparent baseline only, with no tuning, registry, or production artifact management.
- Baseline metrics are implemented as evaluation capabilities, not production performance claims.
- The forecasting runner provides deterministic previews and feature-building persistence, but it is not an orchestrator or scheduled production inference service.
- Dashboard forecast APIs expose persisted records only; they do not provide model serving or scheduled inference.
- No MLflow registry exists.
- P10/P90 may be null and are not treated as guaranteed prediction intervals. The dashboard does not infer missing bands from P50.

## Scenario Limitations

- Scenario outputs are simulations, not predictions.
- Weather adjustment uses a fixed approximation because M05 cannot safely recompute forecasts from changed weather features.
- Humidity assumptions are preserved but do not affect scenario values in this chunk.
- Scenarios do not retrain models or replace M05 forecast rows.

## Briefing Limitations

- Briefings are structured deterministic facts only.
- No LLM narrative generation is implemented.
- Briefings do not send notifications or create tickets.

## Time-Domain Limitations

- IESO hour-ending conversion follows the M01 contract.
- Ambiguous or nonexistent IESO endpoint times are rejected rather than inferred.
- M03-C02A IESO DST alignment can validate spring-forward records that are representable under the current M02 schema.
- The current M02 IESO source-native key uses service date plus hour-ending and cannot fully distinguish the repeated fall-back operating hour without additional source-native detail.
- Real DST transition source behavior must be handled explicitly in future source-specific work.

## Product Limitations

- The M07-C02 fixture fallback is explicitly synthetic or fixture-backed demonstration data and must not be described as live IESO ingestion.
- M07-C02 implements only Overview, Forecasts, Data Quality, Model Performance, System Status, and limitations documentation. Alert, scenario, and briefing screens remain deferred.
- The frontend has no authentication or deployment configuration in this chunk.

GridOps Intelligence is not intended to:

- dispatch electricity resources
- control grid operations
- declare emergencies
- provide reliability certification
- provide energy-trading advice
- replace IESO forecasts
- perform AC or DC power-flow analysis

## Performance Claims

No production forecasting performance claims exist yet. Baseline metric calculations are implemented, but no reliability, uptime, alert-precision, operational-value, or production-model claims should be made before verified production evaluation.
