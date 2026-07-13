# Architecture Decisions

## PostgreSQL is the system of record

PostgreSQL with Alembic is used for integration behavior, persisted evidence, and migration history. SQLite is not substituted where PostgreSQL semantics matter.

## UTC storage with Ontario interpretation

Operational timestamps are timezone-aware UTC, while Ontario views use `America/Toronto`. IESO source-native date and hour-ending fields are retained to preserve traceability and daylight-saving interpretation.

## Evidence before presentation

Forecasts, model metrics, quality outcomes, alerts, scenario outputs, and briefing facts are persisted and serialized by the API. The dashboard reads those contracts rather than calculating equivalent claims in the browser.

## Explicit fixture fallback

Fixture-backed dashboard data is available only when a public configuration flag is set. It is labeled as demonstration data and must not be presented as live IESO activity.

## Public demo safety boundary

Demo mode keeps the dashboard useful without exposing public mutation of alerts or briefing generation. Bounded scenarios are allowed because they use a known forecast, typed inputs, and server-enforced finite limits. This is not an authentication or authorization system.

## Lightweight deployment

The release path favors a Vercel-compatible Next.js frontend, a containerized FastAPI service, and managed PostgreSQL. It avoids unverified cloud infrastructure, Kubernetes, and multi-cloud abstractions.
