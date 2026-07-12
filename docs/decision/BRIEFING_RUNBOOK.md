# M06 Briefing Runbook

## Status

This runbook covers deterministic briefing facts from M06. It does not include free-form LLM narrative generation.

## Briefing Facts

Briefings are generated from structured persisted data only. Supported fact types include:

- `forecast_issue`
- `expected_peak`
- `largest_ramp`
- `open_alert_summary`
- `highest_attention_hours`
- `source_health_summary`
- `quality_limitations`
- `model_confidence_limitations`
- `scenario_highlights`
- `known_limitations`

## Fact Sources

Briefing facts use:

- `production_forecast_runs`
- `production_forecast_predictions`
- `forecast_peak_outputs`
- `forecast_ramp_outputs`
- `alerts`
- M03 source-health summaries from persisted quality runs and results
- `scenario_runs`
- documented limitations

Every persisted `briefing_facts` row includes a JSON fact value and JSON evidence references.

## API Usage

Generate a briefing:

```powershell
POST /briefings/generate
```

Example body:

```json
{
  "production_forecast_run_id": 1,
  "generated_at_utc": "2026-07-10T15:00:00Z"
}
```

Fetch the latest briefing:

```powershell
GET /briefings/latest
```

## Runner Usage

Generate a briefing:

```powershell
uv run python -m gridops.decision.runner generate-briefing --forecast-run-id <forecast_run_id>
```

## Persistence

Tables:

- `briefing_runs`
- `briefing_facts`

Briefing runs preserve:

- base production forecast run ID
- generated timestamp UTC
- briefing version
- fact count
- generation status

## Unsupported Claims

Briefings must not claim:

- official grid emergency status
- causal explanations
- trading recommendations
- replacement of IESO forecasts
- production confidence where M05 has no true interval or confidence signal

## Narrative Behavior

No LLM or free-form narrative generation is implemented in this chunk. The persisted summary records `narrative_generated=false`.

## Current Limitations

- Briefing facts are backend outputs only; no dashboard is implemented.
- Confidence facts are limitation facts because M05 does not generate true prediction intervals.
- Briefings do not send notifications or create tickets.
