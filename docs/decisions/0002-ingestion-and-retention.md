# Decision 0002: bounded OTLP/HTTP ingestion and explicit expiry

- **Status:** accepted for controlled exercise
- **Date:** 2026-11-27

## Context

The pilot needs metrics, logs, traces, and GitHub deployment events with retry/dedup behavior, but does not need a general-purpose collector fleet or production telemetry retention.

## Decision

The sample service exports OTLP/HTTP protobuf directly to the API. The API normalizes a bounded batch, redacts known sensitive values, associates it with a workspace-scoped one-time token/service/incident, deduplicates source records, and stores accepted records in PostgreSQL. Webhooks require repository-specific HMAC verification. Limits are 64 KiB per request, 500 records per batch, 60 OTLP requests/minute/token, and 120 webhook requests/minute. Retain pilot evidence, snapshots, and reports for 30 days by default; allow operator settings 7–365 days. Retain audit events 365 days.

## Consequences

This is the smallest path for an isolated exercise and avoids a collector dependency. It is not intended for untrusted, high-volume or production customer telemetry. Rate limits are persisted in API-side tables and should be moved to an ingress limiter if load testing shows database contention. Sensitive-data cleanup is defense in depth; pilot operators must still send only approved synthetic data.
