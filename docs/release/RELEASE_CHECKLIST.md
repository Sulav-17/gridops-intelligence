# v1.0.0 Release Checklist

## Backend

- [ ] `uv run ruff format --check .`
- [ ] `uv run ruff check .`
- [ ] `uv run mypy src tests`
- [ ] `uv run pytest -q`
- [ ] Clean PostgreSQL migration reaches Alembic head.
- [ ] API smoke-checks `/health`, `/readiness`, `/dashboard/overview`, `/forecasts/latest`, `/quality/health`, `/alerts`, `/model-performance/latest`, `/system/status`, and `/briefings/latest`.

## Frontend

- [ ] `npm.cmd run lint`
- [ ] `npm.cmd run typecheck`
- [ ] `npm.cmd run test`
- [ ] `npm.cmd run build`
- [ ] Dashboard smoke review covers desktop, mobile, empty, unavailable, and fixture-label states.

## Demo and deployment

- [ ] `GRIDOPS_DEMO_MODE=true` returns `403` for alert evaluation, alert lifecycle changes, and briefing generation.
- [ ] A valid bounded scenario is accepted; an out-of-bound scenario is rejected.
- [ ] `GRIDOPS_CORS_ALLOWED_ORIGINS` uses an exact frontend HTTPS origin in production.
- [ ] Backend container builds and `/health` responds after startup.
- [ ] Frontend deployment uses `NEXT_PUBLIC_GRIDOPS_API_BASE_URL` and no local path.

## Security and repository review

- [ ] Run `npm.cmd audit --omit=dev` and record its result; do not apply unsafe automatic remediation.
- [ ] Record advisory ID, installed dependency path, vulnerable and patched ranges, and whether the affected package is direct or transitive.
- [ ] Do not release on an unreviewed audit exception; do not use a breaking downgrade or unsupported override solely to clear the audit.
- [ ] Review Python dependencies with the locked uv environment.
- [ ] Inspect tracked files for `.env` files, API keys, tokens, passwords, private URLs, local absolute paths, raw data, model binaries, caches, and generated files.
- [ ] Confirm only safe example credentials remain in local Docker examples.
- [ ] Confirm public documentation contains no internal workflow, handoff, or milestone-planning material.
- [ ] Review [Known limitations](../../KNOWN_LIMITATIONS.md) and public claims.

## Release readiness and tag

- [ ] Review final verification evidence and merge readiness on `m07`.
- [ ] Merge `m07` into `main` and wait for main CI to pass.
- [ ] Confirm final verification before tagging.

Do **not** run these until the checks above pass on `main`:

```sh
git switch main
git pull --ff-only origin main
git tag -a v1.0.0 -m "GridOps Intelligence v1.0.0"
git push origin v1.0.0
```
