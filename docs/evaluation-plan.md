# Evaluation, testing, security, and operating-cost plan

**Reviewed:** 2026-11-27  
**Current AI status:** harness verified with a transparent mock; live provider comparison pending.

## Dataset and authorship

The frozen evaluation set contains 13 synthetic cases: 3 authored base cases, 6 derived variants, 3 independently authored synthetic scenarios, and 1 missing-deployment-signal case. Eight have a labeled cause and five require abstention. Every case attributes authorship to the Incident Atlas project team; individual authors are not recorded. “Independent” means authored as a separate scenario from the base fixtures, not independently or blindly labeled by an outside expert. The dataset digest is recorded in [`evaluation-report.md`](evaluation-report.md).

Expected labels are loaded only by the scorer after each inference run. Rules and AI adapter receive the same evidence-only packet. No labels, rubric, or expected cause are included in the prompt/packet. Synthetic evaluation files remain separate from runtime evidence and are excluded from the API image.

## Repeatable commands

From `api/` with the locked dev dependencies installed:

```bash
uv run python -m incident_atlas.cli evaluate-expanded
uv run python -m incident_atlas.cli evaluate-ai-rules --mock-provider
```

The default `evaluate-ai-rules` run executes rules and reports the live-provider state as pending without making a network call. `--mock-provider` runs a transparent rules-echo fixture only to check the shared-packet, output parsing, citation validation, abstention, and cost/latency accounting path. It is not model performance. A real provider run requires explicit budget and data-access approval, a configured server-side key, and `--live-provider`.

## Metrics

| Metric | Method |
|---|---|
| Labeled top-1 accuracy | First predicted label equals the case's expected primary label among the eight positive cases. |
| Overall decision accuracy | Correct labeled decision or correct abstention across all 13 cases. |
| Abstention | Correct abstention on five ambiguous/missing/insufficient-signal cases and unnecessary abstention on eight positive cases. |
| Citation validity | Returned evidence IDs belong to the exact packet used for that case. |
| Expected support recall | Returned citations intersect the scorer's expected support set; only scorer-side after inference. |
| Unsupported-claim proxy | Counts a non-abstaining hypothesis when abstention was expected, support is missing/invalid, or support misses all labeled support. Human review is required for actual unsupported-causality classification. |
| Latency | Per-run wall time around the adapter invocation. A mock timing or rules-only timing is not provider/service latency. |
| Cost | Provider-reported tokens plus optional explicitly supplied cost. No current live-provider cost is available. |

## Security and guardrails

- Public Vercel demo remains static, keyless, and backed by bundled synthetic fixtures.
- Hosted pilot users are authenticated via OIDC; the API checks issuer, audience, signature, expiry, and workspace membership on each request. The seeded header identity is development/test-only and rejected in production.
- Every report persists an immutable, workspace-specific snapshot and content hash. Citation reads resolve from that snapshot, not mutable live telemetry.
- OTLP payloads and signed webhooks are bounded; token secrets are stored as hashes. Known sensitive attribute names, emails, card-like values, and bearer/token-like text are redacted. Synthetic data only is permitted for this pilot; sanitization is not a substitute for data approval.
- Live analysis remains off for the pilot. The public demo's simulation-only approval path is unchanged; pilot report UX does not offer mitigation execution.
- Apply workspace queries and endpoint caps on the server. Use parameterized SQLAlchemy queries and additive Alembic migrations. Preserve audit history for 365 days and telemetry/snapshot/report data for the configured 7–365 days (30-day default).

## Checks

CI is expected to run PostgreSQL migration/integration tests, workspace isolation and membership/revocation checks, immutable-citation and expiry checks, ingestion retry/dedup/late/partial/size checks, the disposable database restore test, Ruff, frontend tests/typecheck/build/dependency audit, deterministic evaluation, mock AI harness, container smoke, and browser journeys for the static demo and local pilot. Do not report local PostgreSQL or Docker skips as passes.

## Cost boundary

The public demo costs no model inference. The pilot's current rules baseline makes no provider request. Any future AI comparison must be manually invoked after owner approval; record model/provider, input/output token counts, per-run cost if the provider reports it, latency, failures, and key rotation. Current provider price schedules are not a budget approval. No model-provider credential is configured in this work.
