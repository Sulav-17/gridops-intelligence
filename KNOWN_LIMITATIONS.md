# Known Limitations

- Source ingestion is fixture-backed; the repository does not claim live IESO or weather-provider ingestion.
- No scheduler, Prefect orchestration, dbt transformations, MLflow registry, or managed model serving is implemented.
- P10/P90 fields may be null. The application does not claim true prediction intervals and never derives bands from P50.
- Persisted forecast metrics are evaluation evidence, not proof of operational superiority, reliability, uptime, or business value.
- Scenario outputs are bounded deterministic simulations, not official forecasts. Temperature adjustment uses a documented fixed approximation; humidity may be stored without changing a value.
- Alert severities are project attention signals, not official IESO emergency or reliability categories. There are no notifications, ticketing, or public mutation controls.
- Briefings are persisted deterministic facts only; no LLM narrative generation is implemented.
- The IESO source-native key cannot fully distinguish a repeated fall-back operating hour without additional source detail. Ambiguous or nonexistent endpoint times are rejected instead of inferred.
- The public demo has no authentication and must not be treated as a protected production operations system.
- The documented deployment topology is ready to configure, but no public hosted deployment or live-data verification is claimed.
- The production dependency tree includes `next@16.2.10 -> postcss@8.4.31`. npm reports `GHSA-qx2v-qp2m-jg93` for PostCSS `<8.5.10`; patched releases begin at `8.5.10`. A safe lockfile refresh does not change the exact version Next pins, no compatible Next.js release is currently available, and an unsupported PostCSS override is not used. This is a documented moderate residual dependency risk, not evidence that the application is exploitable.
