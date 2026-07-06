# GridOps Intelligence Project Rules

## 1. Leadership

Samantha is the Project Leader and final authority for:

- milestone scope
- architecture
- sequencing
- milestone approval
- conflict resolution
- cross-milestone decisions

Each milestone is assigned to a named senior engineer.

The assigned engineer leads implementation and review for that milestone but does not independently change the approved project scope.

## 2. Source of Truth

The repository is the authoritative project memory.

Chat history may support the work, but decisions and verified state must be recorded in repository documents.

Important source-of-truth files:

- `CURRENT_STATE.md`
- `ROADMAP.md`
- `ARCHITECTURE.md`
- `DECISIONS.md`
- `KNOWN_LIMITATIONS.md`
- active milestone file
- milestone verification report
- milestone handoff report

Documentation must match repository reality.

## 3. Milestone Model

The project uses one ChatGPT thread per milestone.

Each milestone must:

1. begin from the previous verified repository state
2. remain within its approved scope
3. be divided into testable tickets
4. be verified before approval
5. end with an updated current state
6. produce a verification report
7. produce a handoff for the next milestone

A later milestone must not begin before the current milestone passes its completion gate unless Samantha explicitly approves an exception.

## 4. Ticket Model

Each ticket must define:

- objective
- scope
- acceptance criteria
- expected files
- required tests
- verification commands

After implementation, the engineer must report:

- files changed
- what was implemented
- commands executed
- exact results
- known limitations
- whether acceptance criteria passed

Do not combine unrelated work into one ticket.

## 5. Branching

Recommended branch naming:

- `milestone/m01-foundation`
- `ticket/m01-t01-project-scaffold`

Equivalent clear naming is acceptable.

Rules:

- `main` should represent the latest approved state
- unrelated changes must not be mixed into a ticket
- branches must be understandable from their names
- milestone work should not silently modify future milestone scope

## 6. Engineering Standards

The project must favor:

- correctness over speed
- reproducibility over manual success
- explicit contracts over assumptions
- deterministic logic where possible
- meaningful tests over superficial coverage
- simple designs over unnecessary abstraction
- honest limitations over exaggerated claims

Do not introduce technology only because it may be useful later.

## 7. Verification

A ticket is not complete because code was generated.

Completion requires evidence.

Relevant evidence may include:

- unit-test results
- integration-test results
- migration results
- API responses
- formatting and lint results
- typing results
- CI results
- manual validation
- reproducible commands

Exact commands and results must be recorded.

## 8. Scope Control

Do not implement future milestone work early without approval.

Examples:

- no source ingestion during M01
- no forecasting during M02 or M03
- no production model before trusted backtesting
- no dashboard before stable services
- no unsupported AI narrative generation

Small enabling interfaces are acceptable only when required by the active milestone and clearly documented.

## 9. Escalation to Samantha

Escalate when:

- two reasonable architectures have meaningful long-term consequences
- an approved contract may need to change
- source behavior contradicts project assumptions
- a shortcut could introduce data leakage
- work expands beyond milestone scope
- a stack substitution is proposed
- a database decision creates future-domain entities prematurely
- verification cannot satisfy the completion gate
- engineers disagree on the correct design
- security, privacy, reliability, or deployment risks are unclear

## 10. Documentation Updates

At the end of each approved ticket, update affected documentation.

At the end of each milestone, update at minimum:

- `CURRENT_STATE.md`
- `ROADMAP.md`
- `ARCHITECTURE.md`
- `DECISIONS.md`, when decisions were made
- `KNOWN_LIMITATIONS.md`
- milestone verification report
- milestone handoff report

## 11. Claims

Do not invent:

- model-performance numbers
- reliability claims
- operational outcomes
- user validation
- production readiness
- system-operator equivalence

All public claims must be supported by verified artifacts.