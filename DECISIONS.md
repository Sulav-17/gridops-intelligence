# GridOps Intelligence Decisions

## Decision Format

Each important decision should contain:

- ID
- status
- date
- decision
- context
- alternatives
- rationale
- consequences

---

## DEC-001 - Repository-Based Project Memory

**Status:** Accepted

**Date:** July 2026

### Decision

Repository documents are the authoritative source of truth between milestone threads.

### Context

The project will be developed across multiple ChatGPT threads and engineering sessions. Chat context may become incomplete or unavailable.

### Alternatives

- rely primarily on chat history
- keep informal notes outside the repository
- maintain structured repository state

### Rationale

Repository documentation is versioned, reviewable, and travels with the implementation.

### Consequences

Every milestone must update `CURRENT_STATE.md` and produce verification and handoff documents.

---

## DEC-002 - One Milestone Per Chat Thread

**Status:** Accepted

**Date:** July 2026

### Decision

Each milestone will be developed in a separate ChatGPT project thread.

### Context

The project is large and requires clear context boundaries.

### Alternatives

- one thread for the entire project
- one thread per ticket
- one thread per milestone

### Rationale

One thread per milestone provides enough continuity without allowing the conversation to become unmanageably large.

### Consequences

Milestone handoffs must be complete enough for the next thread to continue from repository evidence.

---

## DEC-003 - Python Version

**Status:** Accepted

**Date:** July 2026

### Decision

The backend uses Python 3.12.

### Context

The project needs a stable modern Python version with broad compatibility across FastAPI, SQLAlchemy, orchestration, MLOps, and machine-learning libraries.

### Alternatives

- Python 3.11
- Python 3.12
- newer versions with less ecosystem maturity

### Rationale

Python 3.12 provides modern language support with strong current ecosystem compatibility.

### Consequences

Development, CI, containers, and documentation should consistently use Python 3.12 unless Samantha approves a change.

---

## DEC-004 - Primary Database

**Status:** Accepted

**Date:** July 2026

### Decision

PostgreSQL is the primary relational database.

### Context

The project requires migrations, normalized operational data, metadata, forecasts, quality results, and monitoring records.

### Alternatives

- SQLite
- PostgreSQL
- cloud warehouse from the beginning

### Rationale

PostgreSQL provides production-relevant relational behavior without forcing unnecessary early cloud complexity.

### Consequences

Local development and CI must support PostgreSQL. SQLite must not be used as a silent replacement for integration behavior.

---

## DEC-005 - Canonical Time Representation

**Status:** Accepted

**Date:** July 2026

### Decision

Canonical operational timestamps use timezone-aware UTC values. Ontario local-time interpretation uses `America/Toronto`.

### Context

Ontario electricity data includes daylight-saving transitions and source-native hour-ending conventions.

### Alternatives

- store local naive timestamps
- store UTC only and discard source-native fields
- store UTC while preserving source-native interpretation fields

### Rationale

UTC provides a stable operational timeline, while preserved source-native fields maintain traceability and correct reconstruction.

### Consequences

Naive datetimes are rejected. Nonexistent Toronto local times are rejected. Ambiguous Toronto local times require an explicit fold choice. IESO hour-ending values are validated and converted as Toronto local hour endpoints.

---

## DEC-006 - Sequential Milestone Delivery

**Status:** Accepted

**Date:** July 2026

### Decision

Milestones will be completed sequentially unless Samantha approves an explicit exception.

### Context

Later work depends on contracts and outputs from earlier milestones.

### Alternatives

- parallel milestone development
- loosely ordered feature development
- sequential milestone gates

### Rationale

Sequential delivery reduces conflicting architecture, data leakage, and rework.

### Consequences

Real ingestion cannot begin before M01 passes, and production modeling cannot begin before trusted data-quality and backtesting foundations exist.

---

## DEC-007 - Application Configuration

**Status:** Accepted

**Date:** July 2026

### Decision

GridOps application settings use Pydantic Settings with strongly typed fields and the `GRIDOPS_` environment-variable prefix. Sensitive configuration values such as the database URL use secret-aware types.

### Context

The application requires consistent configuration across local development, tests, containers, CI, and future deployment environments.

### Alternatives

- untyped direct access through `os.environ`
- custom configuration parsing
- a separate configuration framework
- Pydantic Settings

### Rationale

Pydantic Settings provides typed parsing, validation, environment overrides, clear validation errors, and direct compatibility with the approved FastAPI stack.

### Consequences

Supported environment variables use the `GRIDOPS_` prefix. Invalid ports, environments, log levels, timeouts, and database schemes are rejected. Real credentials must never be stored in repository configuration files.

---

## DEC-008 - Structured Application Logging

**Status:** Accepted

**Date:** July 2026

### Decision

GridOps initially uses Python standard-library logging with a project-owned JSON formatter and explicit secret redaction.

### Context

The project requires consistent machine-readable logs without adding unnecessary infrastructure before application and pipeline behavior exist.

### Alternatives

- plain human-readable logging
- Python logging with structured JSON formatting
- a third-party structured-logging framework
- immediate external logging infrastructure

### Rationale

The standard library provides sufficient reliability and control for M01. A small JSON formatter keeps the implementation inspectable and avoids premature infrastructure dependencies.

### Consequences

Application logs use one-line JSON, UTC timestamps, configuration-driven severity, idempotent initialization, and defensive redaction. External log aggregation remains deferred.

---

## DEC-009 - FastAPI Readiness Scope

**Status:** Accepted

**Date:** July 2026

### Decision

The M01 FastAPI foundation exposes `/health` for process health and `/ready` for real PostgreSQL readiness.

### Context

The application needs a minimal API foundation without implementing product endpoints or future deployment behavior.

### Alternatives

- omit API endpoints until later milestones
- make health and readiness both check PostgreSQL
- expose detailed dependency errors in readiness responses

### Rationale

Separating health from readiness keeps process liveness independent from downstream dependencies, while readiness verifies whether the service can reach PostgreSQL.

### Consequences

`/health` must not touch the database. `/ready` must use real PostgreSQL connectivity and return safe `503` responses without leaking credentials or connection details.

---

## DEC-010 - M01 CI Quality Gates

**Status:** Accepted

**Date:** July 2026

### Decision

GitHub Actions runs the M01 quality gates on Python 3.12 using uv and a PostgreSQL service.

### Context

The foundation needs repeatable verification outside the local development machine.

### Alternatives

- local-only verification
- CI without PostgreSQL
- CI with a separate Docker Compose invocation

### Rationale

A workflow-level PostgreSQL service keeps CI direct while still exercising integration tests and Alembic against PostgreSQL.

### Consequences

CI runs dependency installation, Ruff format check, Ruff lint, MyPy, Pytest, and Alembic current.

---

## DEC-011 - Fixture-First M02 Ingestion Foundation

**Status:** Accepted

**Date:** July 2026

### Decision

M02 implements fixture-backed ingestion first, with persisted raw evidence, ingestion runs, source metadata, hashes, and normalized silver tables.

### Context

The project needs deterministic ingestion behavior before adding live clients, orchestration, or formal data-quality checks.

### Alternatives

- implement live source clients immediately
- add Prefect orchestration in M02
- build fixture-backed ingestion and defer live clients

### Rationale

Fixture-backed ingestion allows repeatable tests, clear time handling, raw evidence preservation, and revision behavior without depending on live internet or unresolved provider choices.

### Consequences

M02 supports only local fixture ingestion through a simple module runner. Live source clients, scheduling, Prefect, dbt, and formal data-quality checks remain deferred to later milestones.
