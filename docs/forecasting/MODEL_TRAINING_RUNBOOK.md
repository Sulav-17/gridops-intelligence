# Model Training Runbook

## Status

M05 implements deterministic candidate training from persisted M04 feature snapshots. This runbook documents the implemented local workflow only.

## Train A Candidate

Dry-run command:

```powershell
uv run python -m gridops.forecasting.production_runner train-candidate --feature-version m04_c01_foundation --training-start-utc 2026-01-01T00:00:00Z --training-end-utc 2026-02-01T00:00:00Z --evaluation-start-utc 2026-02-01T00:00:00Z --evaluation-end-utc 2026-02-08T00:00:00Z --selected-baseline-name same_hour_yesterday --dry-run
```

Database-backed command:

```powershell
$env:GRIDOPS_DATABASE_URL = "postgresql+psycopg://gridops:gridops@127.0.0.1:55432/gridops_test"
uv run python -m gridops.forecasting.production_runner train-candidate --feature-version m04_c01_foundation --training-start-utc 2026-01-01T00:00:00Z --training-end-utc 2026-02-01T00:00:00Z --evaluation-start-utc 2026-02-01T00:00:00Z --evaluation-end-utc 2026-02-08T00:00:00Z --selected-baseline-name same_hour_yesterday
Remove-Item Env:\GRIDOPS_DATABASE_URL
```

## Evaluation

The candidate is evaluated on a time-based evaluation window. Metrics are calculated with the M04 metric logic:

- MAE
- RMSE
- WAPE, when the actual-demand denominator is nonzero
- bias

## Baseline Comparison

Training loads persisted M04 baseline metrics for the configured selected baseline name. The M05 model-selection gate persists either a selected or rejected decision.

## Artifact Storage

Artifacts are local pickle files written under `artifacts/models` by default, or under `GRIDOPS_ARTIFACT_DIR` when configured. Binary artifact files are local development artifacts and must not be committed.

Metadata is persisted to `model_artifacts` with model name, model type, model version, feature version, artifact URI, SHA-256 hash, training window, evaluation window, parameters, metrics, and lineage.

## Feature Versions

Training reads only `feature_snapshot_rows` for the supplied feature version. The M05 candidate uses the M04 payload fields documented in `FEATURE_SNAPSHOT_CONTRACT.md`.

## Window Selection

Training and evaluation windows are caller supplied. The implementation accepts only time-window splits and rejects random split configuration.

## Leakage Prevention

- Feature inputs come from persisted M04 feature snapshot payloads.
- Target actual demand is joined from `ieso_hourly_demand` only as the supervised label.
- Known target-like payload keys are rejected from feature extraction.
- Forecast issue lineage and feature version are preserved.

## Reproducibility

The default candidate is a deterministic scikit-learn gradient boosting regressor with a fixed random state. Training rows are ordered by target interval and persisted snapshot row id.

## Current Limitations

- No LightGBM or XGBoost candidate is implemented.
- No hyperparameter tuning is implemented.
- No MLflow tracking or registry is implemented.
- Training uses locally persisted fixture-backed data.
- No production performance claim is made from these metrics.
