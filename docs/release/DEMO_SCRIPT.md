# GridOps Intelligence Demo Script (3–5 minutes)

## Opening — 20 seconds

“GridOps Intelligence is a production-style portfolio project for Ontario electricity-demand decision support. It connects preserved source evidence, data quality, forecast outputs, alerts, scenarios, and deterministic briefings. It does not control the grid or replace IESO.”

## Overview and forecast — 55 seconds

Open Overview. Point out the latest persisted forecast, peak, ramp, active-alert count, source health, and briefing availability. Open Forecasts and explain that all times are presented in Ontario time while the API preserves UTC. Show P50 and actuals where persisted. State that P10/P90 are shown only when stored and are not inferred.

## Data quality and alerts — 50 seconds

Open Data Quality. Show latest persisted check outcomes, blocking state, and safe notes. Open Alerts and an alert detail. Explain that evidence and lifecycle history are persisted deterministically, and that severities are project attention signals rather than official IESO categories.

## Scenario — 45 seconds

Open Scenarios. Explain public bounds and submit a valid controlled simulation. Show the result summary and the interval comparison table. State that this is a deterministic simulation, not a forecast or model retraining; weather adjustment uses a documented approximation.

## Briefing and model performance — 45 seconds

Open Briefing. Explain that it renders structured persisted facts only, not an LLM narrative. Open Model Performance to show persisted baseline, production-metric, and drift evidence; explicitly mention that unavailable metrics remain unavailable.

## System status and limitations — 30 seconds

Open System Status and explain that safe readiness details are shown without credentials or private infrastructure. Note demo mode and explicit fixture labels. Close by naming absent capabilities: no live ingestion, scheduler, authentication, true prediction intervals, or production-reliability claim.

## Closing — 20 seconds

“This project demonstrates how I approach data products: explicit contracts, reproducible evidence, clear operational UX, and honest boundaries. The repository includes deployment guidance and release verification, while keeping final decisions grounded in verified artifacts.”
