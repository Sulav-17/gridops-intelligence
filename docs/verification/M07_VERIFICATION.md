# M07 Release Verification

## Status

**CONDITIONAL PASS** on branch `m07` at the release-verification working tree. The application checks and clean migration pass. The v1.0.0 tag has not been created and must not be created until `m07` is merged to `main`, main CI passes, and the dependency-audit risk is accepted or remediated compatibly.

## Environment

- Windows PowerShell; Python 3.12; Node.js compatible with Next.js 16.2.10.
- Local PostgreSQL test database: `gridops_test` on `127.0.0.1:55432`.
- Workspace-local uv, temporary, and pytest cache paths were used because the sandbox cannot access the default user cache and Temp directories.

## Backend verification

```text
uv run ruff format --check .
112 files already formatted

uv run ruff check .
All checks passed!

uv run mypy src tests
Success: no issues found in 104 source files

uv run pytest -q
219 passed, 1 warning in 66.10s (0:01:06)
```

The warning is FastAPI/TestClient’s external Starlette deprecation warning for its current HTTPX integration.

Targeted new configuration and API coverage passed: `15 passed, 1 warning in 1.08s`. It covers comma-separated CORS configuration, production wildcard rejection, the `/readiness` probe, and origin behavior.

## Frontend verification

```text
npm.cmd run lint
exit 0

npm.cmd run typecheck
exit 0

npm.cmd run test
3 passed files, 25 passed tests

npm.cmd run build
Next.js 16.2.10 production build completed successfully
```

The production build generated the Overview, Forecasts, Alerts/detail, Data Quality, Scenarios, Briefing, Model Performance, System Status, Documentation, and 404 routes.

## Migration verification

The explicit `gridops_test` database was upgraded, ORM tables and `alembic_version` were dropped, then upgraded again:

```text
uv run alembic upgrade head
dropped ORM tables and alembic_version from gridops_test
uv run alembic upgrade head
uv run alembic current
f7a8b9c0d1e2 (head)
```

All migrations from the empty baseline through the scenario-and-briefing schema applied successfully.

## API and demo-mode smoke verification

With `GRIDOPS_DEMO_MODE=true` against an empty migrated database:

| Request | Result |
| --- | --- |
| `/health` | 200 |
| `/readiness` | 200 |
| `/dashboard/overview` | 200 |
| `/forecasts/latest` | 404 (no succeeded persisted forecast) |
| `/quality/health` | 200 |
| `/alerts` | 200 |
| `/model-performance/latest` | 200 |
| `/system/status` | 200 |
| `/briefings/latest` | 404 (no persisted briefing) |
| `POST /alerts/evaluate` | 403 |
| `PATCH /alerts/1/state` | 403 |
| `POST /briefings/generate` | 403 |
| Out-of-bound `POST /scenarios` | 400 |

`tests/test_dashboard_api.py::test_demo_mode_restricts_mutations_and_bounds_scenarios` also passed (`1 passed, 1 warning in 2.63s`), verifying a valid bounded scenario is accepted and an out-of-bound request is rejected.

## Deployment verification

`docker build -t gridops-intelligence-api:1.0.0 .` completed successfully. The image installs the locked production dependencies, builds the `1.0.0` package, uses the non-root `gridops` user, and exposes the FastAPI factory command. No public hosting environment was provisioned or claimed.

## Dependency and security review

- `uv lock` resolved `uvicorn==0.51.0` and `click==8.4.2`; `uv sync --all-groups` completed successfully.
- `npm.cmd audit --omit=dev` reported **2 moderate vulnerabilities**: PostCSS `<8.5.10` via `next@16.2.10` and `postcss@8.4.31`.
- npm’s only automated remediation is `npm audit fix --force`, which would install breaking downgrade `next@9.3.3`. No unsupported downgrade or automatic remediation was applied.
- Manual tracked-file review checked environment examples, keys/tokens/password patterns, local absolute paths, raw data, model artifacts, generated files, planning files, and historical handoffs. Safe `.env.example` placeholders remain; internal planning/handoff files and the internal master-plan PDF were removed.

## Manual UI review

The production build passed. Existing frontend tests cover dashboard rendering, fallback labels, alerts/evidence/history, scenario bounds and submit states, briefing states, and absence of public mutation/inference controls. Manual browser screenshot capture and public hosting verification remain operator steps; no fake screenshots were added.

## Known limitations and recommendation

No live ingestion, protected authentication, scheduler, MLflow registry, true prediction intervals, grid-control capability, or hosted deployment is claimed. Fixture fallback is explicitly labeled. The dependency-audit finding requires an owner decision because npm offers only a breaking downgrade. Do not tag `v1.0.0` yet.

## Npm audit investigation update

The final registry-backed `npm.cmd audit --omit=dev --json` reports a single advisory, `GHSA-qx2v-qp2m-jg93` (npm advisory source `1117015`), titled “PostCSS has XSS via Unescaped `</style>` in its CSS Stringify Output.” It is reported as two moderate affected entries: direct `next` and transitive `postcss`; it is not two distinct advisories.

| Item | Verified value |
| --- | --- |
| Installed Next.js | `16.2.10` (current stable registry release) |
| Production PostCSS path | `gridops-dashboard -> next@16.2.10 -> postcss@8.4.31` |
| Development PostCSS path | `@vitejs/plugin-react -> vite@8.1.4 -> postcss@8.5.17` |
| PostCSS vulnerable range | `<8.5.10` |
| Patched PostCSS range | `>=8.5.10` |
| Audit affected Next range | `9.3.4-canary.0 - 16.3.0-canary.5` |

PostCSS is not a direct dashboard dependency. Its observed production-tree use is Next’s CSS webpack build block. The audit scopes it as production because Next is a production dependency; this verification does not claim exploitability in this application.

`npm.cmd install` completed with “up to date” and retained the same installed versions. Lint, typecheck, 25 frontend tests, and the Next.js production build all passed afterward. No compatible Next.js patch or minor is available, and no safe lockfile-only remediation exists. `postcss@8.5.18` is available upstream, but adding an npm override would replace the exact `8.4.31` dependency declared by Next without upstream compatibility evidence, so no override was added. `npm audit fix --force` was not run because it proposes `next@9.3.3`, a breaking downgrade.
