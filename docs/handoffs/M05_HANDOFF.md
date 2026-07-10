# M05 Handoff

## Milestone Status

M05 - Production Forecasting and MLOps is complete on branch `m05`, pending review and merge to `main`.

## Implemented Production Forecasting Foundation

- M05 database schema for training runs, artifacts, selection results, forecast runs, forecast predictions, peak outputs, ramp outputs, performance summaries, and drift summaries
- typed contracts for model metadata, forecast outputs, performance summaries, and drift summaries
- local artifact save/load utilities with SHA-256 hashing
- deterministic model-selection gate against persisted M04 baseline metrics
- deterministic sklearn candidate training from M04 feature snapshots
- selected-artifact forecast generation with P50 prediction rows
- peak and ramp forecast output persistence
- model performance and drift monitoring summaries
- simple production runner command boundaries

## Database Tables Added

- `model_training_runs`
- `model_artifacts`
- `model_selection_results`
- `production_forecast_runs`
- `production_forecast_predictions`
- `forecast_peak_outputs`
- `forecast_ramp_outputs`
- `model_performance_summaries`
- `model_drift_summaries`

## Commands Available

Dry-run candidate training:

```powershell
uv run python -m gridops.forecasting.production_runner train-candidate --feature-version m04_c01_foundation --training-start-utc 2026-01-01T00:00:00Z --training-end-utc 2026-02-01T00:00:00Z --evaluation-start-utc 2026-02-01T00:00:00Z --evaluation-end-utc 2026-02-08T00:00:00Z --selected-baseline-name same_hour_yesterday --dry-run
```

Dry-run forecast generation:

```powershell
uv run python -m gridops.forecasting.production_runner generate-forecast --model-artifact-id 1 --forecast-issue-time-utc 2026-02-09T10:00:00Z --dry-run
```

Dry-run monitoring summary:

```powershell
uv run python -m gridops.forecasting.production_runner summarize-monitoring --model-artifact-id 1 --evaluation-start-utc 2026-02-01T00:00:00Z --evaluation-end-utc 2026-02-02T00:00:00Z --baseline-start-utc 2026-01-01T00:00:00Z --baseline-end-utc 2026-01-02T00:00:00Z --comparison-start-utc 2026-02-01T00:00:00Z --comparison-end-utc 2026-02-02T00:00:00Z --dry-run
```

## Candidate Model

The implemented candidate is a deterministic scikit-learn gradient boosting regressor. It uses only approved M04 feature snapshot payload fields and uses actual demand only as the supervised label.

## Model-Selection Gate

The gate requires candidate MAE to be no worse than the selected baseline MAE, WAPE to be no worse when both exist, required lineage fields, and no slice sanity failure.

## Artifact Behavior

Artifacts are local pickle files under an ignored artifact directory. Metadata and hashes are persisted in `model_artifacts`.

## Forecast Output Contract

Forecast outputs persist P50-only predictions, nullable P10/P90 fields, peak output, ramp outputs, and lineage. True quantiles remain deferred.

## Forecast Generation Behavior

Forecast generation loads selected available artifacts only. Rejected artifacts, blocked feature snapshots, missing snapshots, and missing required model inputs fail safely without partial predictions.

## Monitoring Foundation

Performance summaries calculate MAE, RMSE, WAPE, and bias where actuals are available. Drift summaries compare feature means between two windows or persist an explicit no-data summary.

## Known Limitations

- Fixture-backed/local data only.
- No live source clients.
- No LightGBM or XGBoost.
- No MLflow registry.
- No true quantile forecasts.
- No scheduler.
- No production forecast API.
- No alerts, scenarios, briefing generation, dashboard, authentication, deployment, or production performance claims.

## Risks For M06

- M06 should treat M05 forecast outputs as decision-support records, not operational authority.
- Alert thresholds and scenario behavior need explicit product and safety contracts.
- Quantile fields exist but are nullable; M06 must not treat missing intervals as implemented uncertainty.
- Monitoring summaries are foundations only and do not emit alerts.

## Exact Recommended Next Step

After M05 verification passes and the branch is merged, begin M06 by defining alert, scenario, and briefing contracts that consume M05 forecast outputs without adding dashboard or deployment scope.
