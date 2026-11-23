# Incident Atlas

Incident Atlas is a no-sign-in incident investigation demo. Visitors can inspect service dependencies and synthetic telemetry, open a stored investigation replay, follow its evidence references, and record a simulated mitigation approval. Approval changes no external system. Stored replays do not call a model and do not require an API key.

**Public demo:** [incident-atlas-demo.vercel.app](https://incident-atlas-demo.vercel.app/). This is a static frontend-only showcase using bundled synthetic fixtures. It does not connect to FastAPI or PostgreSQL. Simulated approvals are saved in the current browser only; live AI and backend persistence are unavailable.

**GitHub source:** [mrabishekraj2004-cpu/incident-atlas](https://github.com/mrabishekraj2004-cpu/incident-atlas). The static-demo/Vercel setup on main commit [76392ba](https://github.com/mrabishekraj2004-cpu/incident-atlas/commit/76392ba2539781f3b49babb84b80aee94cec5043) passed [GitHub Actions PR run #3](https://github.com/mrabishekraj2004-cpu/incident-atlas/actions/runs/45265136934) before merge. The public URL above was opened and the static replay and browser-local approval flow were verified in production.

## Case study and source

- [Portfolio case study and application screenshots](docs/portfolio-case-study.md)
- [GitHub source repository](https://github.com/mrabishekraj2004-cpu/incident-atlas)
- [Pre-deployment release report](docs/predeployment-release-report.md)
- [Step 6 security and evaluation report](docs/step6-report.md)
- [License decision](docs/licensing-decision.md) — no license has been selected or added.

## Data provenance and evaluation limits

The three incident scenarios and their stored replays are project-authored, deterministic synthetic data shaped like OpenTelemetry records. They are not imported from the OpenTelemetry Demo and are not real production incidents. The separate answer key is absent from the public frontend bundle, public API image, and live model input.

The rules baseline uses three authored base cases, six derived variants, and three independent authored synthetic cases, including expected-abstention cases. Those results describe this small synthetic regression set only; they are not real-world incident accuracy. A separate OpenTelemetry Demo importer is available, but no Demo capture has been imported. Provider coverage is mocked unless a report explicitly records a genuine live model request. No genuine provider run has been verified for the current release.

## Run locally

With Docker Engine and Compose:

```bash
docker compose up --build
```

Open `http://localhost:5173`. Compose starts PostgreSQL, applies migrations and seeds runtime fixtures in a one-shot bootstrap service, then starts the API and web app. The no-key replay journey works with live AI disabled.

To opt into the development fixture preview, copy `web/.env.development.fixture.example` to `web/.env.development.local`. The UI labels this mode **DEV FIXTURE PREVIEW**; it is never selected after an API failure. For the deliberate frontend-only showcase, use the separate `VITE_DATA_MODE=static-demo` build mode described below.

For manual setup, see [API setup](api/README.md) and [web setup](web/README.md). Local checks:

```bash
cd api
uv sync --locked --extra dev --extra observability
uv run pytest -q -rs
uv run ruff check .
uv audit --locked

cd ../web
npm ci
npm test
npm run typecheck
# Frontend-only portfolio build; bundled synthetic fixtures, no API URL.
VITE_DATA_MODE=static-demo npm run build
# Set INCIDENT_ATLAS_API_ORIGIN to a real public HTTPS API origin first.
VITE_API_BASE_URL="${INCIDENT_ATLAS_API_ORIGIN%/}/api/v1" npm run build
npm audit --audit-level=moderate
```

API mode requires an absolute HTTPS API URL ending in `/api/v1`. It rejects reserved example, test, loopback, private, and documentation-only hosts outside the explicit CI placeholder path. The static portfolio mode instead uses bundled synthetic fixture data and requires `VITE_API_BASE_URL` to be unset. Its stored reports never call a model, simulated approvals stay in the current browser, and live AI and backend persistence are unavailable. In a Git checkout, `python scripts/build_release_zip.py --output /tmp/incident-atlas-release.zip` creates and inspects a ZIP from tracked project files while excluding generated output, environments, secrets, caches, and Git metadata.

## Deployment configuration

### Frontend-only Vercel showcase

The public site at [incident-atlas-demo.vercel.app](https://incident-atlas-demo.vercel.app/) serves the React frontend from the `web/` directory. It uses the Vite preset, `npm ci`, `npm run build`, and `dist`, with `VITE_DATA_MODE=static-demo` and no API URL. The checked-in Vercel rewrite supports direct refreshes on React Router paths. The exact setup is in [`web/README.md`](web/README.md).

This static build serves bundled synthetic scenarios and stored replay reports. It does not deploy or call FastAPI or PostgreSQL. Approvals are browser-local; live AI and backend persistence are unavailable. Production was opened in a browser on 23 November 2026; the catalog incident’s six evidence references and browser-local approval survived refresh. No mobile-width visual walkthrough has been completed in the deployed site.

### Optional backend integration

The older API deployment plan uses Render for FastAPI plus PostgreSQL. Its pre-deploy command migrates and seeds with a pinned `MIGRATION_DATABASE_URL`; the API runs with the separate `incident_atlas_runtime` role. Production requires `PUBLIC_SITE_ORIGIN` and `CORS_ALLOWED_ORIGINS` to match the exact frontend HTTPS origin. The runtime role cannot mutate seeded reference data, stored replays, or immutable evidence, and cannot access evaluation data or run migrations. Public model calls have a PostgreSQL-backed global cap; `LIVE_ANALYSIS_ENABLED` remains false in the checked-in deployment template.

The FastAPI service and database remain undeployed. No billable backend resources were created, no model key was configured, and live AI remains disabled. The [staged backend deployment runbook](docs/deployment.md) records the separate migration/runtime credentials and managed-database checks needed before that path can be enabled. See the current [release report](docs/predeployment-release-report.md) for verified outcomes.

## Project blueprint

- [Product requirements and visitor journey](docs/product-requirements.md)
- [Architecture and workflows](docs/architecture.md)
- [API contracts](docs/api-design.md)
- [PostgreSQL data design](docs/data-design.md)
- [Synthetic incident scenarios](docs/incident-scenarios.md)
- [Evaluation plan](docs/evaluation-plan.md)
- [Architecture decisions](docs/decisions.md)
- [Implementation backlog](docs/implementation-backlog.md)
