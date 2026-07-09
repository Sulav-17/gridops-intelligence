# Known Limitations

## Current Repository

The repository contains the completed M01 foundation, M02 ingestion foundation, M03 data quality and observability milestone, and M04 forecasting evaluation foundation.

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

## Missing Capabilities

The following are intentionally not implemented yet:

- live IESO source clients
- live weather provider clients
- scheduled ingestion
- Prefect orchestration
- dbt transformations
- MLflow tracking
- production forecasting models
- quantile forecasts or prediction intervals
- scheduled production inference
- production forecast API
- drift monitoring
- operational alerts
- scenario engine
- briefing generation
- frontend or dashboards
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
- No production forecast API exists.
- No MLflow registry exists.
- No prediction intervals, drift monitoring, alerts, scenarios, dashboard, deployment, or production model serving exist.

## Time-Domain Limitations

- IESO hour-ending conversion follows the M01 contract.
- Ambiguous or nonexistent IESO endpoint times are rejected rather than inferred.
- M03-C02A IESO DST alignment can validate spring-forward records that are representable under the current M02 schema.
- The current M02 IESO source-native key uses service date plus hour-ending and cannot fully distinguish the repeated fall-back operating hour without additional source-native detail.
- Real DST transition source behavior must be handled explicitly in future source-specific work.

## Product Limitations

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
