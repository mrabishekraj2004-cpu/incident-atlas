# Incident Atlas

Incident Atlas is a no-sign-in incident investigation demo. Visitors can inspect service dependencies and synthetic telemetry, open a stored investigation replay, follow its evidence references, and record a simulated mitigation approval. Approval changes no external system. Stored replays do not call a model and do not require an API key.

**Release status:** The source repository and CI are public. The website, API, and PostgreSQL database have not been deployed. There is no live public demo URL. Hosting remains gated on an approved spending cap and account access. Live AI remains disabled until proxy trust, global request limits, and a genuine provider request are verified.

**GitHub source:** [`mrabishekraj2004-cpu/incident-atlas`](https://github.com/mrabishekraj2004-cpu/incident-atlas). The uploaded source snapshot at [`fbaed5909734214f3b237b539eb8d90e571431a6`](https://github.com/mrabishekraj2004-cpu/incident-atlas/commit/fbaed5909734214f3b237b539eb8d90e571431a6) passed [GitHub Actions run #1](https://github.com/mrabishekraj2004-cpu/incident-atlas/actions/runs/45255155052). That run checks the uploaded source snapshot; the Vercel frontend-only preparation described below is local and has not been pushed or deployed.

## Case study and source

- [Portfolio case study and application screenshots](docs/portfolio-case-study.md)
- [GitHub source repository](https://github.com/mrabishekraj2004-cpu/incident-atlas)
- [Pre-deployment release report](docs/predeployment-release-report.md)
- [Step 6 security and evaluation report](docs/step6-report.md)
- [License decision](docs/licensing-decision.md) — no license has been selected or added.

## Data provenance and evaluation limits

The three incident scenarios and their stored replays are project-authored, deterministic synthetic data shaped like OpenTelemetry records. They are not imported from the OpenTelemetry Demo and are not real production incidents. The separate answer key is absent from the public API image and live model input.

The rules baseline uses three authored base cases, six derived variants, and three independent authored synthetic cases, including expected-abstention cases. Those results describe this small synthetic regression set only; they are not real-world incident accuracy. A separate OpenTelemetry Demo importer is available, but no Demo capture has been imported. Provider coverage is mocked unless a report explicitly records a genuine live model request. No genuine provider run has been verified for the current release.

## Run locally

With Docker Engine and Compose:

```bash
docker compose up --build
```

Open `http://localhost:5173`. Compose starts PostgreSQL, applies migrations and seeds runtime fixtures in a one-shot bootstrap service, then starts the API and web app. The no-key replay journey works with live AI disabled.

To opt into the development fixture preview, copy `web/.env.development.fixture.example` to `web/.env.development.local`. The UI labels this mode **DEV FIXTURE PREVIEW**; it is never selected after an API failure. For a deliberate public frontend-only showcase, use the separate `VITE_DATA_MODE=static-demo` build mode described below.

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

API mode requires an absolute HTTPS API URL ending in `/api/v1`. It rejects reserved example, test, loopback, private, and documentation-only hosts outside the explicit CI placeholder path. The static portfolio mode instead uses the bundled synthetic fixture data and requires `VITE_API_BASE_URL` to be unset. Its stored reports never call a model, its simulated approvals stay in the current browser, and live AI and backend persistence are unavailable. In a Git checkout, `python scripts/build_release_zip.py --output /tmp/incident-atlas-release.zip` creates and inspects a ZIP from tracked project files while excluding generated output, environments, secrets, caches, and Git metadata.

## Deployment configuration

### Frontend-only Vercel preview

The React frontend can be deployed by itself from the `web/` directory. Select `web` as Vercel's Root Directory, use the Vite preset, `npm ci`, `npm run build`, and `dist`, then set `VITE_DATA_MODE=static-demo` for Production and Preview. Leave `VITE_API_BASE_URL` unset. Enable **Include source files outside of the Root Directory in the Build Step**, because the frontend imports the shared synthetic incident JSON from `data/incidents/`. The checked-in Vercel rewrite supports direct refreshes on React Router paths. The exact steps are in [`web/README.md`](web/README.md).

This static build serves bundled synthetic scenarios and stored replay reports. It does not deploy or call FastAPI or PostgreSQL. Approvals are browser-local; live AI and backend persistence are unavailable. No Vercel project has been connected and no site has been deployed.

### Optional backend integration

The older API deployment plan uses Render for FastAPI plus PostgreSQL. Its pre-deploy command migrates and seeds with a pinned `MIGRATION_DATABASE_URL`; the API runs with the separate `incident_atlas_runtime` role. Production requires `PUBLIC_SITE_ORIGIN` and `CORS_ALLOWED_ORIGINS` to match the exact frontend HTTPS origin. The runtime role cannot mutate seeded reference data, stored replays, or immutable evidence, and cannot access evaluation data or run migrations. Public model calls have a PostgreSQL-backed global cap; `LIVE_ANALYSIS_ENABLED` remains false in the checked-in deployment template.

No paid resources were created. Before provisioning, approve a spending cap and connect the intended hosting account. The [staged deployment runbook](docs/deployment.md) records how to reserve the Netlify origin first, pin the migration credential before adding the runtime credential, start the API, then build the site with the actual API origin. After deployment, run `python scripts/deployment_smoke.py --api-origin <actual-api-origin> --site-origin <actual-site-origin>` and complete desktop/mobile walkthroughs. See the current [release report](docs/predeployment-release-report.md) for verified outcomes.

## Project blueprint

- [Product requirements and visitor journey](docs/product-requirements.md)
- [Architecture and workflows](docs/architecture.md)
- [API contracts](docs/api-design.md)
- [PostgreSQL data design](docs/data-design.md)
- [Synthetic incident scenarios](docs/incident-scenarios.md)
- [Evaluation plan](docs/evaluation-plan.md)
- [Architecture decisions](docs/decisions.md)
- [Implementation backlog](docs/implementation-backlog.md)
