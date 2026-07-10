# Model Selection

## Status

M05 implements a deterministic model-selection gate against persisted M04 baseline metrics.

## Gate Inputs

The gate requires:

- candidate metrics JSON
- selected baseline metrics JSON
- selected baseline name
- model name, type, and version
- feature version
- training window
- evaluation window
- lineage metadata

## Thresholds

The default gate selects a candidate only when:

- candidate MAE is less than or equal to selected baseline MAE
- candidate WAPE is less than or equal to selected baseline WAPE when both exist
- required lineage fields are present
- no slice sanity failure is present

## Pass Behavior

A passing decision is persisted to `model_selection_results` with `selection_status = selected`, candidate metrics, baseline metrics, reason text, windows, feature version, and lineage.

## Fail Behavior

A failing decision is persisted with `selection_status = rejected`. Rejected artifacts are not usable by forecast generation.

## Lineage Requirements

Required lineage fields:

- `model_name`
- `model_version`
- `feature_version`
- `training_window_start_utc`
- `training_window_end_utc`
- `evaluation_window_start_utc`
- `evaluation_window_end_utc`

## Known Limitations

- The gate is conservative and metric based.
- Slice sanity is represented as explicit candidate metric flags, not a full slice-monitoring workflow.
- No human approval workflow, registry promotion, MLflow registry, deployment record, or alert is implemented.
