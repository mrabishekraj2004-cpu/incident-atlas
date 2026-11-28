# Decision 0001: workspace-scoped evidence with immutable snapshots

- **Status:** accepted for pilot implementation
- **Date:** 2026-11-27

## Context

Two teams need to investigate incidents against shared signals without making a citation mutable or allowing access to another team's records. The public static demo must continue to work without a backend.

## Decision

Keep the public Vercel demo on bundled fixtures and browser-local state. Add a separate FastAPI/PostgreSQL pilot router with explicit workspace and membership keys. Every report copies its evidence into an immutable workspace-owned snapshot and stores its hash. Citation reads resolve from the captured snapshot. Workspace checks are applied on the server on every request. Changes are additive Alembic migrations.

## Consequences

This duplicates a small amount of evidence in the snapshot but makes report provenance inspectable and stable for the configured retention window. Expired report/snapshot/evidence reads are hidden, and an operator cleanup command deletes expired rows. PostgreSQL row-level security is not used; isolation depends on the audited application query boundary plus relational workspace constraints and regression tests.
