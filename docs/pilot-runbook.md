# Two-team pilot runbook

This runbook exercises two isolated synthetic workspaces on one local PostgreSQL instance. The sample services emit OpenTelemetry traces, metrics, and logs over OTLP/HTTP protobuf. The exercise also sends a signed synthetic GitHub `deployment_status` payload. It contacts no GitHub account, does not upload to a real monitoring system, and does not perform remediation.

## Prerequisites and scope

- Docker Compose, Python 3.12, `uv`, Node 22, and npm.
- Ports 5432, 5173, 8000, and 8100 available.
- No provider API key or identity provider is needed for the local exercise.
- Seeded workspaces: `payments-team` / checkout and `platform-team` / catalog. Synthetic identities are local-only; the production API rejects their development header.
- OTLP payloads are capped at 65,536 bytes and 500 normalized records; payloads are processed in one request. Ingest is limited by `PILOT_INGEST_REQUESTS_PER_MINUTE` (default 60) and signed webhooks by `PILOT_WEBHOOK_REQUESTS_PER_MINUTE` (default 120). Duplicate source records are deduplicated by workspace/source/record ID; a repeated idempotency key returns the prior batch response. Late records inside the retention window are accepted and labeled by their event time. Invalid records are counted as rejected while valid records in the batch are kept.
- Default telemetry, snapshots, and saved-report retention is 30 days (operator configuration 7–365 days). Audit history is retained for 365 days; token secrets are only stored as SHA-256 hashes and tokens expire after 90 days by default. `prune` removes expired rows. Reads also hide expired evidence/report/snapshot records immediately.
- The pilot accepts only the four supported signal types and bounded, redacted text/attributes. Do not send customer or production telemetry. Do not include secrets, payment data, personal data, or arbitrary files.

## Start and create private local tokens

From the repository root:

```bash
docker compose up --build -d
docker compose exec api uv run --no-sync python -m incident_atlas.pilot_cli bootstrap-local-env --output /tmp/.env.pilot
docker compose cp api:/tmp/.env.pilot .env.pilot
chmod 600 .env.pilot
docker compose --env-file .env.pilot up -d --force-recreate api web
cd api && uv sync --locked --extra dev --extra observability
cd ..
```

`.env.pilot` contains short-lived local ingestion tokens and webhook secrets. Keep it private and do not commit it. The CLI prints no secret values. If replacing it, use `bootstrap-local-env --force` to revoke and rotate tokens.

## Run the checkout exercise

In terminal A, start the instrumented service:

```bash
set -a
source .env.pilot
set +a
OTEL_SERVICE_NAME="$PILOT_SERVICE_NAME_ALPHA" \
PILOT_INGEST_TOKEN="$PILOT_INGEST_TOKEN_ALPHA" \
PILOT_INCIDENT_ID="$PILOT_INCIDENT_ID_ALPHA" \
uv --project api run --extra observability python -m uvicorn samples.checkout_service.app:app --host 127.0.0.1 --port 8100
```

In terminal B, reset the incident and trigger baseline, deployment, then regression evidence:

```bash
set -a
source .env.pilot
set +a
docker compose --env-file .env.pilot exec api uv run --no-sync python -m incident_atlas.pilot_cli reset --workspace payments-team --incident-key checkout-latency-regression
python scripts/pilot_exercise.py --workspace payments-team
```

Open [http://localhost:5173/pilot?workspace=payments-team](http://localhost:5173/pilot?workspace=payments-team), choose `pilot.payments.editor`, refresh evidence, open an investigation, then follow a citation. Save the exercise JSON output with the rehearsal label; it contains measured local timings but is not a production SLO result.

## Run the comparable catalog exercise

Stop terminal A with Ctrl+C. Start the same service using the platform workspace credentials:

```bash
set -a
source .env.pilot
set +a
OTEL_SERVICE_NAME="$PILOT_SERVICE_NAME_BRAVO" \
PILOT_INGEST_TOKEN="$PILOT_INGEST_TOKEN_BRAVO" \
PILOT_INCIDENT_ID="$PILOT_INCIDENT_ID_BRAVO" \
uv --project api run --extra observability python -m uvicorn samples.checkout_service.app:app --host 127.0.0.1 --port 8100
```

In terminal B:

```bash
set -a
source .env.pilot
set +a
docker compose --env-file .env.pilot exec api uv run --no-sync python -m incident_atlas.pilot_cli reset --workspace platform-team --incident-key catalog-latency-regression
python scripts/pilot_exercise.py --workspace platform-team
```

Open [http://localhost:5173/pilot?workspace=platform-team](http://localhost:5173/pilot?workspace=platform-team), sign in as `pilot.platform.editor`, and repeat the investigation/citation path. Data does not cross the workspace boundary.

## Reset and stop

```bash
docker compose --env-file .env.pilot exec api uv run --no-sync python -m incident_atlas.pilot_cli reset --workspace payments-team --incident-key checkout-latency-regression
docker compose --env-file .env.pilot exec api uv run --no-sync python -m incident_atlas.pilot_cli reset --workspace platform-team --incident-key catalog-latency-regression
docker compose down
```

To remove local database data and credentials after the exercise:

```bash
docker compose down --volumes
rm -f .env.pilot
```

The volume-removal command deletes the local database and is intended only for the disposable local exercise.

## Hosted staging checklist

The optional [Render pilot Blueprint](../render.pilot.yaml) provisions paid services. Require owner approval for the current plan/region and spending limit first. Then configure a maintained OIDC provider, exact HTTPS frontend origin/CORS, isolated PostgreSQL credentials, per-repository webhook secrets, private ingestion tokens, TLS, backup retention, and on-call owner. Disable dev identity and model calls. Reproduce the two-team workflow and recovery test against staging before inviting participants. No staging deployment, real identity connection, or external participant session has been performed by this change.
