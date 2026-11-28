# Decision 0003: maintained OIDC, rules-first analysis, optional hosted pilot

- **Status:** accepted for pilot; hosted deployment pending approval
- **Date:** 2026-11-27

## Context

The public static demo is already available without an account. Two-team access needs authenticated identities, and the requested pilot should not acquire provider cost or execute mitigation.

## Decision

Use `oidc-client-ts` in the browser and validate JWT signature, issuer, audience, expiry, and subject on the API with cached JWKS. The local development identity header is gated off in production. Use the deterministic rules baseline for pilot analysis and preserve evidence gaps/uncertainty. Keep live model analysis disabled. Prepare a separate optional Render API/PostgreSQL Blueprint; do not apply it without explicit spend approval.

## Consequences

The local exercise is reproducible without a real identity provider or model key. Hosted authentication still requires an authorized OIDC issuer, client, redirect URI, and configured subjects. The pilot cannot claim a model advantage or hosted availability before provider evaluation and staging deployment are completed.
