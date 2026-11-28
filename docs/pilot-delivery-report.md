# Evidence-backed pilot delivery report

**Prepared:** 2026-11-28  
**Repository baseline reviewed:** [`8d166fb`](https://github.com/mrabishekraj2004-cpu/incident-atlas/commit/8d166fb0b529256ad34903a81168b2d653fd3ca2)  
**Status:** implementation is complete. Local checks passed where the sandbox permits them. Hosted CI has passed backend, frontend, container, and release-archive jobs; the browser journey is being rerun after a timestamp-ordering fix. Staging is not deployed.

## Starting gaps

The baseline already provided the keyless Vercel static demo, deterministic synthetic incidents, saved replays, immutable replay citations, simulation-only approvals, a FastAPI/PostgreSQL stack, an offline OTLP demonstration importer, and CI. It did not yet provide authenticated team workspaces, workspace-scoped authorization, a persistent ingestion path connecting a sample service and GitHub deployment events to shared incident evidence, or a saved report that snapshots the pilot evidence used for fresh analysis. Deployment documentation described the public demo, while a separate hosted pilot and its operator recovery steps were not ready. Evaluation covered rules regression but not a shared-evidence AI harness; pilot facilitation materials were absent.

## Implemented

- Additive Alembic revision `0005_authenticated_pilot` adds workspaces, memberships, service ownership, incidents, integrations, ingest tokens, evidence, idempotent batch records, immutable report snapshots, saved reports, and audit events. The public demo tables and URLs remain intact.
- The optional pilot API validates OIDC JWTs, enforces owner/editor/viewer roles on the server, and scopes reports, citations, ingestion tokens, and GitHub integrations to a workspace. Development identities are rejected in production.
- A sample checkout/catalog service emits traces, metrics, and logs through OTLP/HTTP. The exercise sends a bounded, HMAC-signed synthetic GitHub `deployment_status` event and then injects a latency regression. Retry, deduplication, late arrivals, partial batch rejects, limits, and missing signals have targeted tests.
- Fresh pilot reports use the deterministic rules baseline, show evidence gaps and uncertainty, and resolve citations against an immutable, hash-stamped evidence snapshot. No model call or mitigation action is made.
- Two sample workspaces, a local reset/trigger path, a React pilot page, CI browser coverage, a separate optional Render Blueprint, SLO proposals, SQL operator queries, outage guidance, and a disposable backup/restore check are included.
- The AI/rules harness evaluates both against the same label-free evidence packet. The mock validates the harness only; a live provider comparison remains pending.
- Facilitator instructions, participant instructions, two comparable synthetic exercises, and a results template are included. No external participant session or feedback is claimed.

## Verification recorded in the workspace

- API regression suite passed. Thirty PostgreSQL-marked cases were skipped because this sandbox cannot start PostgreSQL (`PermissionError: Operation not permitted`); this is not a database integration pass.
- Ruff passed. `uv audit --locked` reported no known vulnerabilities or adverse statuses in 66 packages.
- Frontend tests passed **16/16**; typecheck and Vercel static-demo production build passed. `npm audit --audit-level=moderate` reported **0 vulnerabilities**.
- Offline Alembic SQL generation and Python compilation passed in the preceding review.
- Local Playwright could not run because Chromium is not installed. Docker/PostgreSQL and the disposable restore check were unavailable locally. Hosted CI runs these checks and the complete synthetic pilot browser journey; the latest observed job results are below.
- GitHub Actions run [#29](https://github.com/mrabishekraj2004-cpu/incident-atlas/actions/runs/46118643910) passed `backend-postgres`, `frontend`, `container`, and `release-archive`. The browser check found that whole-second deployment timestamps could place the event after baseline metrics in a fast exercise. The exercise now preserves microseconds in commit [`4371cb8`](https://github.com/mrabishekraj2004-cpu/incident-atlas/commit/4371cb85cc261c0492dde415b0d30bfa207a1498); a fresh browser result is pending.

## Deployment and pilot status

The existing public Vercel site remains the keyless static demo. No FastAPI pilot or PostgreSQL service was deployed. No paid resource was provisioned, no real identity or GitHub account was connected, and no pilot participants were contacted. Hosted staging remains blocked on an explicitly approved spending limit, an operator with deployment access, an OIDC issuer, repository webhook secrets, and participant authorization.

The proposal targets and measurement queries are in [pilot operations](pilot-operations.md). They are targets only; this report contains no production availability, ingestion lag, investigation latency, or recovery-drill measurements. The exact local exercise and reset commands are in the [pilot runbook](pilot-runbook.md). AI evaluation methodology and observed synthetic rules results are in the [evaluation report](evaluation-report.md).
