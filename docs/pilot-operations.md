# Pilot operations and service targets

## Proposed targets (not yet measured in a hosted environment)

| Signal | Proposed target | Measurement |
|---|---:|---|
| API availability | 99.5% per calendar month | Synthetic HTTPS probe of `/readyz` every 30 seconds; count only successful JSON responses under 2 seconds. Exclude planned change windows from the SLO numerator and report them separately. |
| Ingestion lag | p95 ≤ 30 seconds | `created_at - occurred_at` for accepted OTLP evidence, clamped to zero, for the most recent rolling 7 days. Also report p99 and late-arrival count. |
| Investigation latency | p95 ≤ 2 seconds for the rules baseline | API measured analysis duration (`analysis_duration_ms`) for saved reports over the rolling 7 days; separately measure browser end-to-end click-to-render time. The API value excludes network/browser rendering. |

These are initial pilot targets to review after staging traffic and participant workload are known. No availability, ingestion-lag, or investigation-latency result has been measured against a deployed pilot. Sample-service latency from a rehearsal is not a service-level result.

## Retention enforcement

The API hides expired evidence, snapshots, and reports as soon as their expiry passes. The pilot Blueprint also defines a daily 03:17 UTC Render cron job that runs `uv run --no-sync python -m incident_atlas.pilot_cli prune`; it deletes expired evidence, snapshots, reports, batch metadata older than `PILOT_RETENTION_DAYS`, expired ingestion-token hashes, and audit rows older than 365 days. Keep `PILOT_RETENTION_DAYS` in the cron service aligned with the API setting. The job uses the restricted runtime URL for production configuration validation and the owner migration URL for the cleanup transaction. Store both as service secrets; the CLI prints deletion counts only.

The cron service is configured but not deployed. Render cron jobs have a $1/month minimum charge, so applying this part of the Blueprint requires owner approval for that added cost. If the hosted scheduler is not approved, run the same command daily from an authorized operator environment with the API and migration database URLs configured. Expired rows remain hidden from API reads while awaiting cleanup.

## PostgreSQL operator queries

Run read-only queries using an authorized reporting role. They use the default 30-day evidence retention and do not expose payload text.

```sql
-- Accepted OTLP ingestion lag, rolling seven days. Negative clock skew is clamped to zero.
SELECT
  percentile_cont(0.50) WITHIN GROUP (
    ORDER BY GREATEST(0, EXTRACT(EPOCH FROM (created_at - occurred_at)) * 1000)
  ) AS p50_ms,
  percentile_cont(0.95) WITHIN GROUP (
    ORDER BY GREATEST(0, EXTRACT(EPOCH FROM (created_at - occurred_at)) * 1000)
  ) AS p95_ms,
  percentile_cont(0.99) WITHIN GROUP (
    ORDER BY GREATEST(0, EXTRACT(EPOCH FROM (created_at - occurred_at)) * 1000)
  ) AS p99_ms,
  count(*) FILTER (WHERE created_at - occurred_at > interval '30 seconds') AS over_30s
FROM pilot_evidence
WHERE source = 'otel'
  AND created_at >= now() - interval '7 days';

-- Rules investigation latency from the API timer. This is not browser end-to-end latency.
SELECT
  percentile_cont(0.50) WITHIN GROUP (
    ORDER BY (report_payload->>'analysis_duration_ms')::double precision
  ) AS p50_ms,
  percentile_cont(0.95) WITHIN GROUP (
    ORDER BY (report_payload->>'analysis_duration_ms')::double precision
  ) AS p95_ms,
  count(*) AS reports
FROM pilot_reports
WHERE created_at >= now() - interval '7 days'
  AND expires_at > now()
  AND report_payload ? 'analysis_duration_ms';

-- Missing-signal distribution on active evidence. Never group on payload text.
SELECT workspace_id, incident_id, kind, count(*) AS records
FROM pilot_evidence
WHERE expires_at > now()
GROUP BY workspace_id, incident_id, kind
ORDER BY workspace_id, incident_id, kind;
```

The current code does not publish an operational metrics backend or dashboard. Add an external uptime monitor and dashboard before hosted staging; until then these SQL queries are manual diagnostics, not alerts.

## Provider outage behavior

- AI provider: the rules baseline does not call a model. Keep both live-analysis flags off. Saved reports and snapshot citations remain available while the model provider is unavailable; Postgres API availability is still required. The backend contract test captures a report with `model_call_made=false` and resolves its citations locally.
- GitHub: signed events are accepted independently of GitHub's API. Missing deployment events appear as a coverage gap. Do not backfill unverified event payloads. Restore delivery after the webhook/provider is healthy, and expect duplicate deliveries to be deduplicated.
- Telemetry: when ingestion returns a retryable error, retry the same `Idempotency-Key` with the same body. A timeout with unknown outcome can be retried; source-record deduplication protects the timeline. A changed body must use a new idempotency key. Do not retry a 4xx validation error unchanged.
- Database: pause sample service/exporters and webhook delivery at the ingress/proxy if possible; preserve request IDs and sanitized error types. Check `/readyz`, database connectivity, pool saturation, migration state, and storage. Never run schema migration as a manual workaround while the API is serving traffic.

## Backup and restore drill

CI runs `api/tests/test_pilot_backup_restore.py`: it inserts a disposable workspace marker, writes a custom-format `pg_dump`, restores it into a separate disposable PostgreSQL database, verifies the marker, then deletes both test artifacts. The workflow result is the recovery evidence. A local environment without Docker or PostgreSQL reports this test as skipped; it is not a successful restore drill. Render backup policy, restore point, and cutover permissions still require an authorized staging operator.

For an operator drill, restore the managed backup to a temporary database in the same region, run the read-only table-count and citation checks, and confirm the marker workspace/report can be opened through an API connected to that copy. Do not promote the restored database until an incident owner approves the observed point-in-time and integrity check. Record the backup timestamp, restore start/end, counts, citation checks, and any data-loss interval; do not record credentials.
