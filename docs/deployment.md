# Deployment and recovery runbook

**Status reviewed:** 2026-11-27. The public deployment is the static Vercel demo at [incident-atlas-demo.vercel.app](https://incident-atlas-demo.vercel.app/). The FastAPI pilot API and PostgreSQL database are not deployed. The optional pilot Blueprint in [`render.pilot.yaml`](../render.pilot.yaml) would provision paid resources; it has not been applied.

## Deployment map

| Environment | Web | API and database | Identity | Current state |
|---|---|---|---|---|
| Public demo | Vercel static Vite build, bundled synthetic fixtures | None; browser-local demo approvals | None | Existing keyless demo; not connected to the pilot API |
| Local pilot | Vite dev server | FastAPI + PostgreSQL via Compose | Development-only seeded identities | Reproducible controlled exercise; see [pilot runbook](pilot-runbook.md) |
| Hosted pilot | Existing static demo can point at API when built with `VITE_API_BASE_URL` | Optional Render API + managed PostgreSQL | OIDC | Configuration prepared; requires an authorized operator, identity provider setup, and paid resource approval |

The pilot and public demo use separate paths and feature flags. Static demo URLs and bundled data remain compatible. The pilot never performs a real remediation action. Live model analysis remains disabled.

## Hosted pilot setup

Do this only after the project owner approves the Render account, recurring cost ceiling, region, backup plan, identity provider, and staging origin. No paid resource has been provisioned by this work.

1. Review [`render.pilot.yaml`](../render.pilot.yaml) and current Render prices. Create an empty Render Blueprint review; do not apply until the spend is approved.
2. Set the migration and least-privilege runtime PostgreSQL credentials as described in the existing [database deployment design](architecture.md). The migration credential is pinned in `MIGRATION_DATABASE_URL`; `DATABASE_URL` is the restricted runtime role. Never place either in Git.
3. Configure `PILOT_OIDC_ISSUER`, `PILOT_OIDC_AUDIENCE`, and HTTPS `PILOT_OIDC_JWKS_URL`. Add the pilot site origin to both `PUBLIC_SITE_ORIGIN` and the one-item `CORS_ALLOWED_ORIGINS` list. Set the matching Vite build variable to the API URL plus `/api/v1`.
4. Configure `GITHUB_WEBHOOK_SECRETS` as a JSON object keyed by exact `owner/repository`; use a new random secret per repository. Configure the deployment webhook for `deployment_status`, and register the repository-to-workspace integration with the owner CLI. Pilot event bodies are bounded and HMAC checked.
5. Apply the Blueprint only after the approved review, then record actual hostnames, commit SHA, deployment IDs, migration result, and smoke result in the release report. Run [`scripts/deployment_smoke.py`](../scripts/deployment_smoke.py) and complete both workspace exercises against the hosted origin.
6. Keep `LIVE_ANALYSIS_ENABLED=false` and `LIVE_PROVIDER_VERIFIED=false`. Do not add an AI-provider key for this pilot unless the separate model budget and data-access review are approved.

## Rollback

- Static demo: redeploy the last known good Vercel commit. It does not depend on pilot service health.
- Pilot frontend: restore the last build from the API-compatible commit or remove the pilot feature flag. Do not point the static-demo build at the API.
- Pilot API: redeploy the last API image. The server does not migrate on process start. For an additive migration, first roll back the API image; leave additive columns/tables in place until a reviewed follow-up cleanup migration is safe.
- Database: pause ingestion, capture a provider/database incident note, restore the latest verified backup into a disposable database first, and compare workspace/evidence/report counts before any recovery cutover. Keep the original database immutable until the owner accepts the recovery result.
- Identity or GitHub outage: continue to use the Vercel synthetic demo. Existing API-hosted snapshot/report reads need the API and database but do not call GitHub or the model provider.

## Readiness checks

Run local checks from the repository root:

```bash
cd api && uv run alembic upgrade head
cd ..
cd web && npm ci && npm test && npm run typecheck
```

The full CI workflow also builds the API container, starts PostgreSQL-backed browser tests, runs the Vercel-safe static build, executes the browser demo, and runs backup/restore verification in a disposable database. A green local static build is not evidence that the hosted pilot has deployed. See [pilot operations and targets](pilot-operations.md).
