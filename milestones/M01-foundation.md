# M01 — Domain Contract and Foundation

## Ownership

**Senior Owner:** Ethan Cole  
**Role:** Senior Platform Engineer  
**Project Leader:** Samantha

## Status

Active

## Objective

Create a reproducible repository, backend API, database foundation, local development environment, CI pipeline, configuration system, logging system, and explicit electricity-time contract.

M01 must create a stable foundation for all later ingestion, validation, forecasting, monitoring, and product work.

## Completion Statement

M01 succeeds when a developer can clone the repository, create a clean Python 3.12 environment, start PostgreSQL, apply migrations, run the API, verify liveness and readiness, run all supported quality checks, and reproduce documented UTC, Toronto-time, DST, and IESO hour-ending behavior.

## Included Scope

M01 includes:

- Python 3.12 project setup
- src-based package structure
- dependency management
- FastAPI application foundation
- health endpoint
- readiness endpoint
- Pydantic settings
- structured logging
- PostgreSQL
- SQLAlchemy 2.x
- Alembic
- Docker Compose
- Ruff
- MyPy
- Pytest
- HTTPX-based API testing
- GitHub Actions CI
- time-domain documentation
- time-domain utilities
- DST tests
- IESO hour-ending tests
- milestone verification
- milestone handoff

## Excluded Scope

M01 must not implement:

- real IESO ingestion
- weather ingestion
- raw snapshot storage workflows
- Prefect orchestration
- dbt models
- source-quality pipelines
- feature engineering
- forecasting models
- MLflow
- alerts
- scenarios
- briefing generation
- Next.js frontend
- production deployment

Do not create future domain tables prematurely.

## Approved Core Stack

- Python 3.12
- FastAPI
- Pydantic
- Pydantic Settings
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- HTTPX
- Pytest
- Ruff
- MyPy
- Docker Compose
- GitHub Actions

Any meaningful substitution requires Samantha's approval.

# Ticket Plan

## M01-T01 — Repository and Python Foundation

### Objective

Create a clean, reproducible Python project and establish the repository quality-tooling foundation.

### Expected Work

- create a src-based Python package
- define project metadata
- define runtime and development dependencies
- configure Python 3.12
- configure Ruff
- configure MyPy
- configure Pytest
- create `.gitignore`
- create `.env.example`
- document supported local commands
- add minimal import and test evidence

### Expected Structure

```text
src/
  gridops/
    __init__.py

tests/

pyproject.toml
.env.example
.gitignore


The final structure may differ slightly when justified.

Acceptance Criteria
project installs in a clean Python 3.12 environment
gridops imports successfully
Ruff formatting check runs
Ruff linting runs
MyPy runs
Pytest runs
commands are documented
no unrelated application features are added
M01-T02 — Configuration and Structured Logging
Objective

Create strongly typed application configuration and safe, consistent logging.

Expected Work

Configuration should cover at minimum:

application name
application environment
log level
API host or port where appropriate
database URL
readiness settings where appropriate

Logging should:

initialize consistently
support structured output
avoid exposing credentials
be testable
avoid complex external logging infrastructure
Acceptance Criteria
documented defaults work
environment overrides work
invalid configuration fails clearly
secrets are not logged
logging initializes consistently
configuration tests pass
M01-T03 — FastAPI Application Foundation
Objective

Create a testable FastAPI application with trustworthy liveness and readiness behavior.

Required Endpoints
GET /health

Purpose:

Process-level liveness.

Requirements:

must not require PostgreSQL
must return success while the application process is healthy
must use a defined response schema
must not expose internal implementation details
GET /ready

Purpose:

Required-dependency readiness.

Requirements:

must check PostgreSQL connectivity
must return success when required dependencies are available
must return a non-success readiness response when PostgreSQL is unavailable
must not expose credentials or raw database errors
Expected Work
application factory or similarly testable structure
health route
readiness route
consistent response schemas
OpenAPI generation
route tests
safe dependency-failure behavior
Acceptance Criteria
application can be created in tests
health succeeds independently of the database
readiness succeeds with PostgreSQL
readiness fails safely without PostgreSQL
OpenAPI schema generates
endpoint tests pass
M01-T04 — PostgreSQL, SQLAlchemy, Alembic, and Docker
Objective

Create the local relational-database foundation and migration workflow.

Expected Work
PostgreSQL through Docker Compose
SQLAlchemy 2.x engine configuration
session management
database connectivity utility
Alembic configuration
initial migration
documented startup and migration commands
database integration testing
Schema Boundary

Do not design ingestion, forecast, model, alert, or scenario tables during M01.

The initial migration may be minimal.

A schema-version or other small foundation table is permitted only when clearly justified.

An empty baseline migration is acceptable when it provides a clean migration foundation and is verified.

Acceptance Criteria
Docker Compose starts PostgreSQL
application connects to PostgreSQL
Alembic upgrades an empty database
downgrade and re-upgrade behavior is verified where practical
database test configuration is isolated
readiness uses real database connectivity
clean-checkout instructions are reproducible
M01-T05 — UTC, Toronto Time, DST, and IESO Hour-Ending Contract
Objective

Establish explicit and tested rules for electricity-domain time handling.

This ticket is a critical foundation for M02 and all later forecasting work.

Required Rules

The implementation and documentation must cover:

canonical UTC timestamp storage
America/Toronto local-time interpretation
timezone-aware datetime requirements
policy for rejecting or explicitly localizing naive datetimes
source-native date retention
source-native IESO hour-ending retention
interval-start derivation
interval-end derivation
spring daylight-saving transition
fall daylight-saving transition
23-hour Ontario local days
25-hour Ontario local days
ambiguous local timestamps
nonexistent local timestamps
publication-time retention
retrieval-time retention
API timestamp serialization
database timestamp conventions
IESO Hour-Ending Requirement

An IESO hour-ending field represents the end label of an electricity interval.

It must not be treated as a normal zero-based clock-hour field.

The implementation must preserve enough source-native evidence to reconstruct how a record was interpreted.

Where official behavior remains uncertain:

document the assumption
isolate the conversion boundary
do not silently guess
escalate consequential uncertainty to Samantha
Required Test Categories
normal winter date
normal summer date
regular hour-ending conversion
end-of-day hour-ending conversion
spring-forward transition
fall-back transition
ambiguous local timestamp
nonexistent local timestamp
deterministic UTC output
machine-timezone independence
timezone-aware API serialization
Acceptance Criteria
time rules are documented
timezone-aware values are enforced
naive datetime behavior is explicit
representative hour-ending conversions pass
spring transition tests pass
fall transition tests pass
23-hour and 25-hour behavior is represented
UTC conversion is deterministic
tests do not depend on the developer machine's timezone
M01-T06 — CI and Repository Quality Gates
Objective

Create automated quality verification for clean repository checkouts.

Required CI Checks
install dependencies
Ruff formatting check
Ruff linting
MyPy
Pytest

Where integration tests require PostgreSQL, CI should provide a PostgreSQL service.

CI Rules
run on appropriate pushes and pull requests
fail when a required check fails
use stable action versions
avoid fragile unnecessary complexity
use the same commands documented for local development
Acceptance Criteria
CI runs from a clean checkout
all required checks execute
database tests run reliably
failed checks fail the workflow
local and CI commands are aligned
CI passes on the milestone branch
M01-T07 — Full Verification and Handoff
Objective

Verify M01 from a clean state and prepare M02 to begin safely.

Required Automated Verification
clean dependency installation
package import
Ruff formatting check
Ruff linting
MyPy
full Pytest suite
database integration tests
migration execution
time-domain tests
CI result
Required Manual Verification
start PostgreSQL
apply migrations
start FastAPI
request /health
request /ready with PostgreSQL available
verify /ready behavior with PostgreSQL unavailable
inspect generated OpenAPI schema
review logs for secret exposure
review repository for accidental credentials
review scope for future-milestone work
verify documentation commands
Required Documents

Create:

docs/verification/M01_VERIFICATION.md
docs/handoffs/M01_HANDOFF.md

Update:

CURRENT_STATE.md
ROADMAP.md
ARCHITECTURE.md
DECISIONS.md
KNOWN_LIMITATIONS.md
README.md
Verification Report Must Include
environment
branch
commit
commands executed
exact results
test totals
migration results
API validation results
time-contract validation
CI status
security review
limitations
failures or corrections
Handoff Must Include
milestone status
completed tickets
architecture established
important commands
configuration behavior
database state
migration state
time-domain contract
exact test evidence
known limitations
deferred work
M02 risks
exact recommended next action
M01 Completion Gate

M01 is complete only when:

the repository installs reproducibly
the application starts successfully
/health behaves correctly
/ready reflects real dependency availability
PostgreSQL runs through Docker Compose
SQLAlchemy connectivity is verified
Alembic works from an empty database
configuration and logging are operational
Ruff passes
MyPy passes
Pytest passes
GitHub Actions passes
UTC and Toronto-time rules are documented
DST behavior is tested
IESO hour-ending behavior is documented and tested
documentation matches repository reality
verification and handoff documents are complete
Samantha approves the milestone
Escalation Conditions

Escalate to Samantha when:

official IESO time behavior remains uncertain
a time decision affects future storage design
a proposed table belongs to a future milestone
the approved stack may need to change
a shortcut weakens DST correctness
CI requires a major platform change
ingestion work is proposed during M01
the completion gate cannot be met without changing scope
Engineer Reporting Format

After each ticket, report:

Ticket:
Status:
Files changed:
What was implemented:
Acceptance criteria:
Verification commands:
Verification results:
Issues found:
Known limitations:
Decision:
Next recommended ticket:
Final M01 Review Format
M01 status: PASS, CONDITIONAL PASS, or FAIL

Completed deliverables:
Automated verification:
Manual verification:
Architecture review:
Time-contract review:
Configuration and security review:
Documentation review:
Known limitations:
Deferred work:
M02 readiness:
Required corrections:
Recommendation to Samantha:

---

# 10. Commit the governance files

After creating them:

```powershell
git add .
git commit -m "docs: initialize GridOps project governance"

Then create the M01 branch:

git switch -c milestone/m01-foundation

Do not create ticket branches yet. Ethan should first inspect the repository and confirm the ticket breakdown.