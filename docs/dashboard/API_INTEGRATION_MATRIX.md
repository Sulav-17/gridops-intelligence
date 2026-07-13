# Dashboard API Reference

The dashboard reads persisted evidence from a compact FastAPI surface. It does not calculate forecasts, metrics, alerts, quality results, scenarios, or briefing facts in the browser.

| Route | Purpose | Empty or unavailable behavior |
| --- | --- | --- |
| `GET /dashboard/overview` | Latest forecast, peak/ramp, alert count, source health, briefing availability | Forecast and briefing may be absent. |
| `GET /forecasts/latest` | Latest successful forecast and hourly persisted values | Returns `404` when no succeeded run exists. |
| `GET /forecasts/{id}` | One forecast record, actuals when available, peak and ramps | P10/P90 may be null; no band is inferred. |
| `GET /quality/health` | Safe quality and source-health summary | Returns safe `503` on database failure. |
| `GET /alerts` and `GET /alerts/{id}` | Deterministic alert records, evidence, and lifecycle history | Empty list or `404` is represented in the UI. |
| `POST /scenarios` and `GET /scenarios/{id}` | Bounded persisted planning simulations | Scenario outputs are simulations, not forecasts. |
| `GET /briefings/latest` | Latest structured deterministic facts | Returns `404` when none exists. |
| `GET /model-performance/latest` | Persisted baseline, monitoring, and drift evidence | Missing metrics stay unavailable. |
| `GET /system/status` | Safe database state, demo mode, and run timestamps | Never exposes credentials or private host details. |

`/health` is a process-health probe and `/readiness` verifies PostgreSQL readiness. `/ready` is retained as a compatibility alias.

## Public demo restrictions

With `GRIDOPS_DEMO_MODE=true`, reads remain available. `POST /alerts/evaluate`, `PATCH /alerts/{id}/state`, and `POST /briefings/generate` return `403`. `POST /scenarios` is allowed only for finite typed inputs within configured inclusive limits. This is a safety boundary for a public demonstration, not authentication.

## Frontend configuration

`NEXT_PUBLIC_GRIDOPS_API_BASE_URL` selects the API origin. The frontend falls back to typed fixture data only when `NEXT_PUBLIC_GRIDOPS_USE_DEMO_DATA=true` and visibly identifies it as fixture-backed demonstration data.
