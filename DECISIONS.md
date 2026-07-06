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

## DEC-001 — Repository-Based Project Memory

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

## DEC-002 — One Milestone Per Chat Thread

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

## DEC-003 — Python Version

**Status:** Accepted

**Date:** July 2026

### Decision

The backend will use Python 3.12.

### Context

The project needs a stable modern Python version with broad compatibility across FastAPI, SQLAlchemy, Prefect, MLflow, and machine-learning libraries.

### Alternatives

- Python 3.11
- Python 3.12
- newer versions with less ecosystem maturity

### Rationale

Python 3.12 provides modern language support with strong current ecosystem compatibility.

### Consequences

Development, CI, containers, and documentation should consistently use Python 3.12 unless Samantha approves a change.

---

## DEC-004 — Primary Database

**Status:** Accepted

**Date:** July 2026

### Decision

PostgreSQL will be the primary relational database.

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

## DEC-005 — Canonical Time Representation

**Status:** Accepted in principle; implementation pending M01

**Date:** July 2026

### Decision

Canonical operational timestamps will be stored as timezone-aware UTC values. Ontario local-time interpretation will use `America/Toronto`.

### Context

Ontario electricity data includes daylight-saving transitions and source-native hour-ending conventions.

### Alternatives

- store local naive timestamps
- store UTC only and discard source-native fields
- store UTC while preserving source-native interpretation fields

### Rationale

UTC provides a stable operational timeline, while preserved source-native fields maintain traceability and correct reconstruction.

### Consequences

M01 must define and test ambiguous, nonexistent, 23-hour, and 25-hour local-time behavior before ingestion begins.

---

## DEC-006 — Sequential Milestone Delivery

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