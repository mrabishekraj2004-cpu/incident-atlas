"""Authenticated, tenant-scoped pilot API alongside the keyless public demo."""

# FastAPI declares dependencies in parameter defaults by design.
# ruff: noqa: B008

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from time import perf_counter
from typing import Any, Literal

import jwt
from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from incident_atlas.config import Settings, get_settings
from incident_atlas.db import get_db
from incident_atlas.errors import ApiError
from incident_atlas.models import (
    GuestRateEvent,
    PilotAuditEvent,
    PilotEvidence,
    PilotIncident,
    PilotIngestBatch,
    PilotIngestToken,
    PilotIntegration,
    PilotMembership,
    PilotReport,
    PilotService,
    PilotSnapshot,
    PilotSnapshotEvidence,
    PilotWorkspace,
)

logger = logging.getLogger("incident_atlas.pilot")
SENSITIVE_KEY = re.compile(
    r"(?:email|user[._-]?id|card|cvv|password|passwd|passphrase|token|secret|"
    r"api[._-]?key|access[._-]?token|refresh[._-]?token|authorization|cookie|"
    r"session|address|phone|ssn|credential)",
    re.IGNORECASE,
)
BEARER_TEXT = re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]+")
API_TOKEN_TEXT = re.compile(
    r"(?i)\b(?:sk|rk|pk|ghp|gho|ghu|ghs|glpat|github_pat|xox[baprs])[-_]"
    r"[A-Za-z0-9_-]{12,}"
)
EMAIL_TEXT = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
SENSITIVE_VALUE_TEXT = re.compile(
    r"(?i)\b(password|passwd|passphrase|token|secret|authorization|api[_-]?key|"
    r"card(?:[_-]?number)?|cvv)\b(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^,\s;]+)"
)
CARD_VALUE_TEXT = re.compile(
    r"(?i)\b(card(?:[_-]?number)?|cvv)\b(\s*[:=]\s*)(?:\d[ -]?){3,19}"
)
CARD_NUMBER_TEXT = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
MAX_BODY_BYTES = 65_536


def _pilot_enabled(settings: Settings = Depends(get_settings)) -> None:
    if not settings.pilot_enabled:
        raise ApiError(404, "pilot_disabled", "The authenticated workspace pilot is not enabled.")


router = APIRouter(
    prefix="/api/v1/pilot",
    tags=["authenticated pilot"],
    dependencies=[Depends(_pilot_enabled)],
)


@dataclass(frozen=True)
class Principal:
    subject: str


def _problem(status: int, code: str, detail: str) -> ApiError:
    return ApiError(status, code, detail)


@lru_cache(maxsize=8)
def _jwk_client(jwks_url: str) -> jwt.PyJWKClient:
    # The JWKS is cached so read-only workspace/report requests survive a short
    # identity-provider outage. Keys refresh at most hourly.
    return jwt.PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=3600, timeout=2)


def _authenticate(request: Request, settings: Settings) -> Principal:
    if settings.pilot_dev_auth_enabled and settings.environment.lower() in {
        "development",
        "test",
    }:
        subject = request.headers.get("x-atlas-dev-user", "").strip()
        if subject:
            if len(subject) > 240 or any(ord(char) < 32 for char in subject):
                raise _problem(401, "invalid_identity", "The development identity is invalid.")
            return Principal(subject=subject)

    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token or not settings.pilot_oidc_issuer:
        raise _problem(
            401, "authentication_required", "Sign in with the configured identity provider."
        )
    if not settings.pilot_oidc_audience or not settings.pilot_oidc_jwks_url:
        raise _problem(
            503, "identity_not_configured", "The workspace identity provider is not configured."
        )
    try:
        signing_key = _jwk_client(settings.pilot_oidc_jwks_url).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=settings.pilot_oidc_audience,
            issuer=settings.pilot_oidc_issuer,
            options={"require": ["exp", "iss", "aud", "sub"]},
            leeway=30,
        )
        subject = claims["sub"]
        if not isinstance(subject, str) or not subject or len(subject) > 240:
            raise jwt.InvalidTokenError("invalid subject")
        return Principal(subject=subject)
    except (jwt.PyJWTError, jwt.PyJWKClientError, OSError, TimeoutError) as exc:
        logger.info("pilot_auth_rejected error_type=%s", type(exc).__name__)
        raise _problem(
            401, "invalid_access_token", "The sign-in token is invalid or expired."
        ) from None


def _membership(
    db: Session,
    settings: Settings,
    request: Request,
    workspace_id: str,
    allowed_roles: tuple[str, ...] = ("owner", "editor", "viewer"),
) -> tuple[Principal, PilotMembership]:
    actor = _authenticate(request, settings)
    member = db.scalar(
        select(PilotMembership).where(
            PilotMembership.workspace_id == workspace_id,
            PilotMembership.subject == actor.subject,
        )
    )
    if member is None:
        # Deliberately do not disclose whether the workspace exists.
        raise _problem(404, "workspace_not_found", "The workspace does not exist.")
    if member.role not in allowed_roles:
        raise _problem(403, "permission_denied", "Your workspace role does not allow this action.")
    return actor, member


def _incident(db: Session, workspace_id: str, incident_id: str) -> PilotIncident:
    incident = db.scalar(
        select(PilotIncident).where(
            PilotIncident.workspace_id == workspace_id,
            PilotIncident.id == incident_id,
        )
    )
    if incident is None:
        raise _problem(404, "incident_not_found", "The incident does not exist in this workspace.")
    return incident


def _audit(
    db: Session,
    request: Request,
    workspace_id: str,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    attributes: dict[str, Any] | None = None,
) -> None:
    db.add(
        PilotAuditEvent(
            id=f"audit_{uuid.uuid4().hex}",
            workspace_id=workspace_id,
            subject=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            request_id=getattr(request.state, "request_id", "unknown"),
            occurred_at=datetime.now(UTC),
            attributes=attributes or {},
        )
    )


def _consume_rate_event(
    db: Session,
    subject: str,
    action: str,
    limit: int,
    now: datetime,
) -> None:
    subject_hash = hashlib.sha256(subject.encode()).hexdigest()
    # Serialize the check-and-insert pair per subject/action. The transaction
    # lock is released by the commit below, so a concurrent request sees the
    # event inserted by the previous request before checking the limit.
    lock_key = f"pilot-rate:{action}:{subject_hash}"
    db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(lock_key, 0))))
    count = (
        db.scalar(
            select(func.count())
            .select_from(GuestRateEvent)
            .where(
                GuestRateEvent.subject_hash == subject_hash,
                GuestRateEvent.action == action,
                GuestRateEvent.occurred_at > now - timedelta(minutes=1),
            )
        )
        or 0
    )
    if count >= limit:
        raise ApiError(
            429,
            "pilot_rate_limited",
            "The pilot request limit was reached; retry after one minute.",
            True,
        )
    db.add(GuestRateEvent(subject_hash=subject_hash, action=action, occurred_at=now))
    db.commit()


def _iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _workspace_out(row: PilotWorkspace, role: str) -> dict[str, Any]:
    return {"id": row.id, "name": row.name, "role": role}


def _incident_out(db: Session, row: PilotIncident) -> dict[str, Any]:
    now = datetime.now(UTC)
    service = db.scalar(
        select(PilotService).where(
            PilotService.workspace_id == row.workspace_id,
            PilotService.id == row.primary_service_id,
        )
    )
    coverage = {
        record[0]: record[1]
        for record in db.execute(
            select(PilotEvidence.kind, func.count(PilotEvidence.id))
            .where(
                PilotEvidence.workspace_id == row.workspace_id,
                PilotEvidence.incident_id == row.id,
                PilotEvidence.expires_at > now,
            )
            .group_by(PilotEvidence.kind)
        ).all()
    }
    return {
        "id": row.id,
        "incident_key": row.incident_key,
        "title": row.title,
        "severity": row.severity,
        "summary": row.summary,
        "status": row.status,
        "started_at": _iso(row.started_at),
        "workspace_id": row.workspace_id,
        "service": {
            "id": service.id if service else row.primary_service_id,
            "name": service.service_name if service else row.primary_service_id,
            "owner_team": service.owner_team if service else "unassigned",
        },
        "signal_counts": coverage,
        "missing_signals": [
            name for name in ("metric", "log", "trace", "deploy") if not coverage.get(name)
        ],
    }


@router.get("/workspaces")
def list_workspaces(
    request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> dict[str, Any]:
    actor = _authenticate(request, settings)
    rows = db.execute(
        select(PilotWorkspace, PilotMembership.role)
        .join(PilotMembership, PilotMembership.workspace_id == PilotWorkspace.id)
        .where(PilotMembership.subject == actor.subject)
        .order_by(PilotWorkspace.id)
    ).all()
    return {"items": [_workspace_out(workspace, role) for workspace, role in rows]}


@router.get("/workspaces/{workspace_id}/incidents")
def list_workspace_incidents(
    workspace_id: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _membership(db, settings, request, workspace_id)
    rows = db.scalars(
        select(PilotIncident)
        .where(PilotIncident.workspace_id == workspace_id)
        .order_by(PilotIncident.started_at.desc(), PilotIncident.id)
    ).all()
    return {"items": [_incident_out(db, row) for row in rows]}


@router.get("/workspaces/{workspace_id}/incidents/{incident_id}")
def get_workspace_incident(
    workspace_id: str,
    incident_id: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _membership(db, settings, request, workspace_id)
    incident = _incident(db, workspace_id, incident_id)
    return _incident_out(db, incident)


@router.get("/workspaces/{workspace_id}/incidents/{incident_id}/timeline")
def get_workspace_timeline(
    workspace_id: str,
    incident_id: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _membership(db, settings, request, workspace_id)
    _incident(db, workspace_id, incident_id)
    now = datetime.now(UTC)
    rows = db.scalars(
        select(PilotEvidence)
        .where(
            PilotEvidence.workspace_id == workspace_id,
            PilotEvidence.incident_id == incident_id,
            PilotEvidence.expires_at > now,
        )
        .order_by(PilotEvidence.occurred_at, PilotEvidence.id)
        .limit(2000)
    ).all()
    return {
        "items": [
            {
                "evidence_id": row.id,
                "kind": row.kind,
                "source": row.source,
                "service_id": row.service_id,
                "occurred_at": _iso(row.occurred_at),
                "title": str(
                    row.payload.get("title")
                    or row.payload.get("metric_name")
                    or row.payload.get("operation")
                    or row.payload.get("summary")
                    or row.kind.title()
                ),
                "summary": str(
                    row.payload.get("summary")
                    or row.payload.get("message")
                    or row.payload.get("description")
                    or row.payload.get("metric_name")
                    or row.payload.get("operation")
                    or "Evidence record"
                ),
                "payload": row.payload,
            }
            for row in rows
        ]
    }


@router.get("/workspaces/{workspace_id}/services")
def list_workspace_services(
    workspace_id: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _membership(db, settings, request, workspace_id)
    rows = db.scalars(
        select(PilotService)
        .where(PilotService.workspace_id == workspace_id)
        .order_by(PilotService.service_name)
    ).all()
    return {
        "items": [
            {
                "id": row.id,
                "name": row.service_name,
                "owner_team": row.owner_team,
                "description": row.description,
            }
            for row in rows
        ]
    }


@router.get("/workspaces/{workspace_id}/members")
def list_workspace_members(
    workspace_id: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _membership(db, settings, request, workspace_id)
    rows = db.scalars(
        select(PilotMembership)
        .where(PilotMembership.workspace_id == workspace_id)
        .order_by(PilotMembership.subject)
    ).all()
    return {"items": [{"subject": row.subject, "role": row.role} for row in rows]}


@router.put("/workspaces/{workspace_id}/members/{subject:path}")
def set_workspace_member_role(
    workspace_id: str,
    subject: str,
    request: Request,
    body: dict[str, str],
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    actor, _ = _membership(db, settings, request, workspace_id, ("owner",))
    role = body.get("role")
    if role not in {"owner", "editor", "viewer"} or len(subject) > 240:
        raise _problem(
            422, "invalid_membership", "Provide a valid subject and owner, editor, or viewer role."
        )
    existing = db.scalar(
        select(PilotMembership).where(
            PilotMembership.workspace_id == workspace_id,
            PilotMembership.subject == subject,
        )
    )
    if existing is None:
        existing = PilotMembership(
            workspace_id=workspace_id, subject=subject, role=role, created_at=datetime.now(UTC)
        )
        db.add(existing)
        action = "member_added"
    else:
        action = "member_role_changed"
        if existing.role == "owner" and role != "owner":
            owner_count = (
                db.scalar(
                    select(func.count())
                    .select_from(PilotMembership)
                    .where(
                        PilotMembership.workspace_id == workspace_id,
                        PilotMembership.role == "owner",
                    )
                )
                or 0
            )
            if owner_count <= 1:
                raise _problem(
                    409, "last_owner_required", "A workspace must keep at least one owner."
                )
        existing.role = role
    _audit(db, request, workspace_id, actor.subject, action, "membership", subject, {"role": role})
    db.commit()
    return {"subject": subject, "role": role}


@router.delete("/workspaces/{workspace_id}/members/{subject:path}", status_code=204)
def remove_workspace_member(
    workspace_id: str,
    subject: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> None:
    actor, _ = _membership(db, settings, request, workspace_id, ("owner",))
    member = db.scalar(
        select(PilotMembership).where(
            PilotMembership.workspace_id == workspace_id,
            PilotMembership.subject == subject,
        )
    )
    if member is None:
        raise _problem(404, "member_not_found", "The member does not exist in this workspace.")
    if member.role == "owner":
        owner_count = (
            db.scalar(
                select(func.count())
                .select_from(PilotMembership)
                .where(
                    PilotMembership.workspace_id == workspace_id,
                    PilotMembership.role == "owner",
                )
            )
            or 0
        )
        if owner_count <= 1:
            raise _problem(409, "last_owner_required", "A workspace must keep at least one owner.")
    db.delete(member)
    _audit(db, request, workspace_id, actor.subject, "member_removed", "membership", subject)
    db.commit()


def _evidence_id(workspace_id: str, source: str, source_record_id: str) -> str:
    """Keep evidence primary keys tenant-scoped even when upstream ids overlap."""
    identity = f"{workspace_id}\0{source}\0{source_record_id}".encode()
    return "evidence:" + hashlib.sha256(identity).hexdigest()


@router.patch("/workspaces/{workspace_id}/services/{service_id}/owner")
def change_service_owner(
    workspace_id: str,
    service_id: str,
    request: Request,
    body: dict[str, str],
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    actor, _ = _membership(db, settings, request, workspace_id, ("owner",))
    service = db.scalar(
        select(PilotService).where(
            PilotService.workspace_id == workspace_id, PilotService.id == service_id
        )
    )
    team = body.get("owner_team", "").strip()
    if service is None:
        raise _problem(404, "service_not_found", "The service does not exist in this workspace.")
    if not team or len(team) > 120:
        raise _problem(422, "invalid_owner", "A service owner team is required.")
    service.owner_team = team
    _audit(
        db,
        request,
        workspace_id,
        actor.subject,
        "service_owner_changed",
        "service",
        service_id,
        {"owner_team": team},
    )
    db.commit()
    return {"id": service.id, "owner_team": service.owner_team}


@router.get("/workspaces/{workspace_id}/audit")
def get_workspace_audit(
    workspace_id: str,
    request: Request,
    limit: int = 100,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _membership(db, settings, request, workspace_id)
    audit_floor = datetime.now(UTC) - timedelta(days=365)
    rows = db.scalars(
        select(PilotAuditEvent)
        .where(
            PilotAuditEvent.workspace_id == workspace_id,
            PilotAuditEvent.occurred_at >= audit_floor,
        )
        .order_by(PilotAuditEvent.occurred_at.desc(), PilotAuditEvent.id)
        .limit(min(max(limit, 1), 200))
    ).all()
    return {
        "items": [
            {
                "id": row.id,
                "subject": row.subject,
                "action": row.action,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "occurred_at": _iso(row.occurred_at),
                "attributes": row.attributes,
            }
            for row in rows
        ]
    }


def _snapshot_items(db: Session, workspace_id: str, incident_id: str) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    rows = db.scalars(
        select(PilotEvidence)
        .where(
            PilotEvidence.workspace_id == workspace_id,
            PilotEvidence.incident_id == incident_id,
            PilotEvidence.expires_at > now,
        )
        .order_by(PilotEvidence.occurred_at, PilotEvidence.id)
        .limit(2000)
    ).all()
    return [
        {
            "evidence_id": row.id,
            "kind": row.kind,
            "source": row.source,
            "service_id": row.service_id,
            "observed_at": _iso(row.occurred_at),
            "payload": row.payload,
        }
        for row in rows
    ]


def _rules_report(
    incident: PilotIncident, items: list[dict[str, Any]], snapshot_id: str, snapshot_sha: str
) -> dict[str, Any]:
    deploys = [item for item in items if item["kind"] == "deploy"]
    latency = [
        item
        for item in items
        if item["kind"] == "metric"
        and any(
            word in str(item["payload"].get("metric_name", "")).lower()
            for word in ("latency", "duration")
        )
        and isinstance(item["payload"].get("value"), (int, float))
    ]
    gaps = [
        name
        for name, kind in (
            ("metrics", "metric"),
            ("logs", "log"),
            ("traces", "trace"),
            ("GitHub deployment event", "deploy"),
        )
        if not any(item["kind"] == kind for item in items)
    ]
    hypotheses: list[dict[str, Any]] = []
    service_name = incident.primary_service_id
    uncertainty = (
        "The rules baseline abstained because the snapshot does not contain a deployment plus "
        "comparable latency samples before and after it."
    )
    if deploys and latency:
        deploy_at = min(
            datetime.fromisoformat(item["observed_at"].replace("Z", "+00:00")) for item in deploys
        )
        before = [
            item
            for item in latency
            if datetime.fromisoformat(item["observed_at"].replace("Z", "+00:00")) <= deploy_at
        ]
        after = [
            item
            for item in latency
            if datetime.fromisoformat(item["observed_at"].replace("Z", "+00:00")) > deploy_at
        ]
        if before and after:
            before_mean = sum(float(item["payload"]["value"]) for item in before) / len(before)
            after_mean = sum(float(item["payload"]["value"]) for item in after) / len(after)
            ratio = after_mean / max(before_mean, 0.001)
            if ratio >= 1.5:
                support = [deploys[0]["evidence_id"], *[item["evidence_id"] for item in after[:3]]]
                correlated = [
                    item
                    for item in items
                    if item["kind"] in {"trace", "log"}
                    and datetime.fromisoformat(item["observed_at"].replace("Z", "+00:00"))
                    >= deploy_at
                ]
                support.extend(item["evidence_id"] for item in correlated[:2])
                hypotheses.append(
                    {
                        "id": f"hypothesis_{uuid.uuid4().hex[:16]}",
                        "rank": 1,
                        "statement": (
                            f"Latency for {service_name} increased after the recorded deployment; "
                            "this is "
                            "a temporal correlation, not proof that the deployment caused the "
                            "regression."
                        ),
                        "confidence": "medium",
                        "confidence_note": (
                            f"Observed latency summary increased {ratio:.1f}× across "
                            f"{len(before)} pre-deploy and {len(after)} post-deploy metric "
                            "points. The sample is small and correlation does not establish cause."
                        ),
                        "supporting_evidence_ids": sorted(set(support)),
                        "contradicting_evidence_ids": [],
                        "next_read_only_check": (
                            f"Compare the {service_name} deployment diff and trace span attributes "
                            "with a "
                            "controlled rollback-free canary; do not execute a mitigation "
                            "from this report."
                        ),
                        "mitigation": {
                            "id": "simulated-checkout-review",
                            "summary": (
                                "Simulation only: review the deployed change and compare a "
                                "controlled canary."
                            ),
                        },
                    }
                )
                uncertainty = (
                    "The evidence supports a deployment-time association. It does not establish "
                    "causality; inspect the linked trace attributes and deployment diff."
                )
    return {
        "id": f"report_{uuid.uuid4().hex}",
        "incident_id": incident.id,
        "workspace_id": incident.workspace_id,
        "source": "rules_fresh_analysis",
        "analysis_mode": "rules_baseline",
        "model_call_made": False,
        "evidence_snapshot_id": snapshot_id,
        "evidence_snapshot_sha256": snapshot_sha,
        "captured_evidence_count": len(items),
        "evidence_gaps": gaps,
        "uncertainty": uncertainty,
        "hypotheses": hypotheses,
        "simulation_only": True,
        "external_action_performed": False,
    }


@router.post("/workspaces/{workspace_id}/incidents/{incident_id}/investigations", status_code=201)
def create_workspace_investigation(
    workspace_id: str,
    incident_id: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    actor, _ = _membership(db, settings, request, workspace_id, ("owner", "editor"))
    started = perf_counter()
    incident = _incident(db, workspace_id, incident_id)
    items = _snapshot_items(db, workspace_id, incident_id)
    canonical = json.dumps(
        items, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    snapshot_sha = hashlib.sha256(canonical).hexdigest()
    now = datetime.now(UTC)
    snapshot_id = f"pilot-snapshot-{uuid.uuid4().hex}"
    snapshot = PilotSnapshot(
        id=snapshot_id,
        workspace_id=workspace_id,
        incident_id=incident_id,
        created_at=now,
        sha256=snapshot_sha,
        item_count=len(items),
        expires_at=now + timedelta(days=settings.pilot_retention_days),
    )
    db.add(snapshot)
    # The snapshot must exist before its evidence rows because PostgreSQL
    # enforces the composite workspace foreign key immediately.
    db.flush()
    for item in items:
        db.add(
            PilotSnapshotEvidence(
                snapshot_id=snapshot_id,
                evidence_id=item["evidence_id"],
                workspace_id=workspace_id,
                kind=item["kind"],
                source=item["source"],
                service_id=item["service_id"],
                observed_at=datetime.fromisoformat(item["observed_at"].replace("Z", "+00:00")),
                payload=item["payload"],
            )
        )
    db.flush()
    report_payload = _rules_report(incident, items, snapshot_id, snapshot_sha)
    report_payload["created_at"] = _iso(now)
    report_payload["analysis_duration_ms"] = round((perf_counter() - started) * 1000, 3)
    report = PilotReport(
        id=report_payload["id"],
        workspace_id=workspace_id,
        incident_id=incident_id,
        snapshot_id=snapshot_id,
        source=report_payload["source"],
        report_payload=report_payload,
        created_at=now,
        expires_at=now + timedelta(days=settings.pilot_retention_days),
    )
    db.add(report)
    _audit(
        db,
        request,
        workspace_id,
        actor.subject,
        "investigation_created",
        "report",
        report.id,
        {"snapshot_sha256": snapshot_sha, "evidence_count": len(items)},
    )
    db.commit()
    return report_payload


@router.get("/workspaces/{workspace_id}/incidents/{incident_id}/reports")
def list_workspace_reports(
    workspace_id: str,
    incident_id: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _membership(db, settings, request, workspace_id)
    _incident(db, workspace_id, incident_id)
    now = datetime.now(UTC)
    rows = db.scalars(
        select(PilotReport)
        .where(
            PilotReport.workspace_id == workspace_id,
            PilotReport.incident_id == incident_id,
            PilotReport.expires_at > now,
        )
        .order_by(PilotReport.created_at.desc())
        .limit(100)
    ).all()
    return {"items": [row.report_payload for row in rows]}


@router.get("/workspaces/{workspace_id}/reports/{report_id}")
def get_workspace_report(
    workspace_id: str,
    report_id: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _membership(db, settings, request, workspace_id)
    now = datetime.now(UTC)
    report = db.scalar(
        select(PilotReport).where(
            PilotReport.workspace_id == workspace_id,
            PilotReport.id == report_id,
            PilotReport.expires_at > now,
        )
    )
    if report is None:
        raise _problem(
            404, "report_not_found", "The saved report does not exist in this workspace."
        )
    return report.report_payload


@router.get("/workspaces/{workspace_id}/snapshots/{snapshot_id}/evidence/{evidence_id}")
def get_workspace_evidence(
    workspace_id: str,
    snapshot_id: str,
    evidence_id: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _membership(db, settings, request, workspace_id)
    now = datetime.now(UTC)
    snapshot = db.scalar(
        select(PilotSnapshot).where(
            PilotSnapshot.workspace_id == workspace_id,
            PilotSnapshot.id == snapshot_id,
            PilotSnapshot.expires_at > now,
        )
    )
    evidence = db.scalar(
        select(PilotSnapshotEvidence).where(
            PilotSnapshotEvidence.workspace_id == workspace_id,
            PilotSnapshotEvidence.snapshot_id == snapshot_id,
            PilotSnapshotEvidence.evidence_id == evidence_id,
        )
    )
    if snapshot is None or evidence is None:
        raise _problem(
            404, "evidence_not_found", "The citation does not exist in this saved snapshot."
        )
    return {
        "evidence_id": evidence.evidence_id,
        "kind": evidence.kind,
        "source": evidence.source,
        "service_id": evidence.service_id,
        "observed_at": _iso(evidence.observed_at),
        "snapshot_id": snapshot.id,
        "snapshot_sha256": snapshot.sha256,
        "payload": evidence.payload,
    }


def _require_json_body(raw: bytes, signal: str) -> Any:
    if not raw:
        raise _problem(400, "empty_telemetry_batch", "The telemetry batch is empty.")
    if len(raw) > MAX_BODY_BYTES:
        raise _problem(
            413, "telemetry_batch_too_large", "The telemetry batch exceeds the 64 KiB limit."
        )
    try:
        from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
            ExportLogsServiceRequest,
        )
        from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
            ExportMetricsServiceRequest,
        )
        from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
            ExportTraceServiceRequest,
        )
    except ModuleNotFoundError:
        raise _problem(
            503,
            "otel_ingestion_unavailable",
            "Install the observability extra to accept OTLP data.",
        ) from None
    request_type = {
        "traces": ExportTraceServiceRequest,
        "metrics": ExportMetricsServiceRequest,
        "logs": ExportLogsServiceRequest,
    }[signal]
    message = request_type()
    try:
        message.ParseFromString(raw)
    except Exception:
        raise _problem(
            422, "invalid_otlp_payload", "The body is not a valid OTLP protobuf request."
        ) from None
    return message


def _proto_value(value: Any) -> Any:
    variant = value.WhichOneof("value")
    if variant == "string_value":
        return _clean_text(value.string_value)
    if variant == "kvlist_value":
        return _proto_attributes(value.kvlist_value.values)
    if variant == "array_value":
        return [_proto_value(item) for item in value.array_value.values]
    if variant == "bytes_value":
        return "[redacted-bytes]"
    return getattr(value, variant) if variant else None


def _proto_attributes(attributes: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in attributes:
        if item.key and not SENSITIVE_KEY.search(item.key):
            result[item.key] = _proto_value(item.value)
    return result


def _clean_text(value: str, maximum: int = 2048) -> str:
    cleaned = BEARER_TEXT.sub(r"\1[redacted]", value)
    cleaned = API_TOKEN_TEXT.sub("[redacted-token]", cleaned)
    cleaned = EMAIL_TEXT.sub("[redacted-email]", cleaned)
    cleaned = CARD_VALUE_TEXT.sub(r"\1\2[redacted]", cleaned)
    cleaned = SENSITIVE_VALUE_TEXT.sub(r"\1\2[redacted]", cleaned)
    cleaned = CARD_NUMBER_TEXT.sub("[redacted-number]", cleaned)
    return cleaned[:maximum]


def _timestamp(nanos: int) -> datetime | None:
    try:
        if not nanos:
            return None
        return datetime.fromtimestamp(nanos / 1_000_000_000, tz=UTC)
    except (ValueError, OverflowError, OSError):
        return None


def _resource_service(resource: Any) -> str:
    for attribute in resource.attributes:
        if attribute.key == "service.name":
            value = _proto_value(attribute.value)
            if isinstance(value, str):
                return value
    return ""


def _normalise_otlp(message: Any, signal: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if signal == "traces":
        for group in message.resource_spans:
            service_name = _resource_service(group.resource)
            for scope in group.scope_spans:
                for span in scope.spans:
                    observed = _timestamp(span.start_time_unix_nano)
                    ended = _timestamp(span.end_time_unix_nano)
                    trace_id, span_id = span.trace_id.hex(), span.span_id.hex()
                    if (
                        not observed
                        or not ended
                        or not trace_id.strip("0")
                        or not span_id.strip("0")
                    ):
                        continue
                    status = {0: "UNSET", 1: "OK", 2: "ERROR"}.get(span.status.code, "UNSET")
                    records.append(
                        {
                            "source_record_id": f"trace:{trace_id}:{span_id}",
                            "service_name": service_name,
                            "kind": "trace",
                            "occurred_at": observed,
                            "payload": {
                                "trace_id": trace_id,
                                "span_id": span_id,
                                "parent_span_id": span.parent_span_id.hex()
                                if span.parent_span_id
                                else None,
                                "operation": _clean_text(span.name, 240),
                                "duration_ms": round((ended - observed).total_seconds() * 1000, 3),
                                "status": status,
                                "attributes": _proto_attributes(span.attributes),
                            },
                        }
                    )
    elif signal == "metrics":
        for group in message.resource_metrics:
            service_name = _resource_service(group.resource)
            for scope_index, scope in enumerate(group.scope_metrics):
                for metric_index, metric in enumerate(scope.metrics):
                    family = metric.WhichOneof("data")
                    if not family:
                        continue
                    points = getattr(metric, family).data_points
                    for point_index, point in enumerate(points):
                        observed = _timestamp(point.time_unix_nano or point.start_time_unix_nano)
                        if not observed:
                            continue
                        if family in {"gauge", "sum"}:
                            value_kind = point.WhichOneof("value")
                            if value_kind not in {"as_double", "as_int"}:
                                raise _problem(
                                    422,
                                    "invalid_metric_point",
                                    "A gauge or sum point must contain a numeric value.",
                                )
                            value = float(getattr(point, value_kind))
                        elif family in {"histogram", "exponential_histogram"}:
                            value = float(point.sum / point.count) if point.count else 0.0
                        elif family == "summary":
                            value = float(point.sum / point.count) if point.count else 0.0
                        else:
                            continue
                        attrs = _proto_attributes(point.attributes)
                        stable = json.dumps(
                            [
                                service_name,
                                metric.name,
                                observed.isoformat(),
                                scope_index,
                                metric_index,
                                point_index,
                                attrs,
                            ],
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        records.append(
                            {
                                "source_record_id": "metric:"
                                + hashlib.sha256(stable.encode()).hexdigest(),
                                "service_name": service_name,
                                "kind": "metric",
                                "occurred_at": observed,
                                "payload": {
                                    "metric_name": _clean_text(metric.name, 240),
                                    "value": value,
                                    "unit": metric.unit or "1",
                                    "statistic": family,
                                    "labels": attrs,
                                },
                            }
                        )
    else:
        for group in message.resource_logs:
            service_name = _resource_service(group.resource)
            for scope in group.scope_logs:
                for row in scope.log_records:
                    observed = _timestamp(row.time_unix_nano or row.observed_time_unix_nano)
                    if not observed:
                        continue
                    body = _proto_value(row.body)
                    body_text = _clean_text(str(body or ""))
                    stable = json.dumps(
                        [
                            service_name,
                            row.time_unix_nano,
                            row.observed_time_unix_nano,
                            row.trace_id.hex(),
                            row.span_id.hex(),
                            body_text,
                        ],
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    records.append(
                        {
                            "source_record_id": "log:"
                            + hashlib.sha256(stable.encode()).hexdigest(),
                            "service_name": service_name,
                            "kind": "log",
                            "occurred_at": observed,
                            "payload": {
                                "severity": row.severity_text or str(row.severity_number),
                                "message": body_text,
                                "trace_id": row.trace_id.hex() if row.trace_id else None,
                                "span_id": row.span_id.hex() if row.span_id else None,
                                "attributes": _proto_attributes(row.attributes),
                            },
                        }
                    )
    return records


def _ingest_token(db: Session, authorization: str, now: datetime) -> PilotIngestToken:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or len(token) < 32:
        raise _problem(
            401, "ingest_authentication_required", "A workspace-scoped ingestion token is required."
        )
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    row = db.scalar(
        select(PilotIngestToken).where(
            PilotIngestToken.token_hash == token_hash,
            PilotIngestToken.revoked_at.is_(None),
            PilotIngestToken.expires_at > now,
        )
    )
    if row is None:
        raise _problem(
            401, "invalid_ingest_token", "The ingestion token is invalid, expired, or revoked."
        )
    return row


@router.post("/ingest/otel/v1/{signal}")
async def ingest_otel(
    signal: Literal["traces", "metrics", "logs"],
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    authorization: str = Header(default=""),
    incident_id: str = Header(default="", alias="X-Atlas-Incident-Id"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    now = datetime.now(UTC)
    token = _ingest_token(db, authorization, now)
    _consume_rate_event(
        db,
        f"ingest:{token.id}",
        "pilot_ingest",
        settings.pilot_ingest_requests_per_minute,
        now,
    )
    incident = _incident(db, token.workspace_id, incident_id)
    raw = await request.body()
    if len(raw) > min(settings.pilot_max_payload_bytes, MAX_BODY_BYTES):
        raise _problem(
            413, "telemetry_batch_too_large", "The telemetry batch exceeds the configured limit."
        )
    message = _require_json_body(raw, signal)
    records = _normalise_otlp(message, signal)
    if len(records) > settings.pilot_max_ingest_records:
        raise _problem(
            413,
            "too_many_telemetry_records",
            "The batch contains more records than the configured limit.",
        )
    payload_sha = hashlib.sha256(raw).hexdigest()
    batch_key = (idempotency_key or payload_sha)[:160]
    lock_key = f"{token.workspace_id}:{incident.id}:{signal}:{batch_key}"
    db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(lock_key, 0))))
    existing_batch = db.scalar(
        select(PilotIngestBatch).where(
            PilotIngestBatch.workspace_id == token.workspace_id,
            PilotIngestBatch.incident_id == incident.id,
            PilotIngestBatch.signal == signal,
            PilotIngestBatch.idempotency_key == batch_key,
        )
    )
    if existing_batch is not None:
        if existing_batch.payload_sha256 != payload_sha:
            raise _problem(
                409,
                "idempotency_key_reused",
                "The idempotency key was already used for a different telemetry body.",
            )
        return {
            "signal": signal,
            "accepted": 0,
            "duplicates": existing_batch.accepted_count + existing_batch.duplicate_count,
            "rejected": existing_batch.rejected_count,
            "idempotent_replay": True,
            "late_arrivals": 0,
        }

    service_names = {
        row.service_name: row
        for row in db.scalars(
            select(PilotService).where(PilotService.workspace_id == token.workspace_id)
        ).all()
    }
    source_record_ids = {record["source_record_id"] for record in records}
    existing_source_record_ids = (
        set(
            db.scalars(
                select(PilotEvidence.source_record_id).where(
                    PilotEvidence.workspace_id == token.workspace_id,
                    PilotEvidence.source == "otel",
                    PilotEvidence.source_record_id.in_(source_record_ids),
                )
            ).all()
        )
        if source_record_ids
        else set()
    )
    accepted = duplicates = rejected = late = 0
    retention_floor = now - timedelta(days=settings.pilot_retention_days)
    expires_at = now + timedelta(days=settings.pilot_retention_days)
    for record in records:
        occurred_at = record["occurred_at"]
        service = service_names.get(record["service_name"])
        if (
            service is None
            or service.id != token.service_id
            or occurred_at < retention_floor
            or occurred_at > now + timedelta(minutes=5)
        ):
            rejected += 1
            continue
        if occurred_at < now - timedelta(minutes=15):
            late += 1
        source_record_id = record["source_record_id"]
        if source_record_id in existing_source_record_ids:
            duplicates += 1
            continue
        values = {
            "id": _evidence_id(token.workspace_id, "otel", source_record_id),
            "workspace_id": token.workspace_id,
            "incident_id": incident.id,
            "service_id": service.id,
            "kind": record["kind"],
            "source": "otel",
            "source_record_id": source_record_id,
            "occurred_at": occurred_at,
            "payload": record["payload"],
            "created_at": now,
            "expires_at": expires_at,
        }
        result = db.execute(
            insert(PilotEvidence)
            .values(**values)
            .on_conflict_do_nothing(constraint="uq_pilot_evidence_dedupe")
        )
        if result.rowcount:
            accepted += 1
        else:
            duplicates += 1
        existing_source_record_ids.add(source_record_id)
    batch = PilotIngestBatch(
        id=f"batch_{uuid.uuid4().hex}",
        workspace_id=token.workspace_id,
        incident_id=incident.id,
        signal=signal,
        idempotency_key=batch_key,
        payload_sha256=payload_sha,
        accepted_count=accepted,
        duplicate_count=duplicates,
        rejected_count=rejected,
        created_at=now,
    )
    db.add(batch)
    _audit(
        db,
        request,
        token.workspace_id,
        f"ingest:{token.id}",
        "telemetry_ingested",
        "incident",
        incident.id,
        {"signal": signal, "accepted": accepted, "duplicates": duplicates, "rejected": rejected},
    )
    db.commit()
    return {
        "signal": signal,
        "accepted": accepted,
        "duplicates": duplicates,
        "rejected": rejected,
        "idempotent_replay": False,
        "late_arrivals": late,
    }


@router.post("/workspaces/{workspace_id}/integrations/github")
def register_github_integration(
    workspace_id: str,
    request: Request,
    body: dict[str, str],
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    actor, _ = _membership(db, settings, request, workspace_id, ("owner",))
    repository = body.get("repository", "").strip().lower()
    incident_key = body.get("incident_key", "").strip()
    if repository.count("/") != 1 or len(repository) > 240 or not incident_key:
        raise _problem(
            422,
            "invalid_github_integration",
            "Provide a repository as owner/name and a workspace incident key.",
        )
    if repository not in settings.github_webhook_secrets:
        raise _problem(
            409,
            "github_webhook_secret_missing",
            "Configure the matching GitHub webhook secret in the API environment first.",
        )
    incident = db.scalar(
        select(PilotIncident).where(
            PilotIncident.workspace_id == workspace_id, PilotIncident.incident_key == incident_key
        )
    )
    if incident is None:
        raise _problem(
            404, "incident_not_found", "The selected incident does not exist in this workspace."
        )
    integration = PilotIntegration(
        id=f"github_{uuid.uuid4().hex}",
        workspace_id=workspace_id,
        provider="github",
        external_id=repository,
        incident_key=incident_key,
        enabled=True,
        created_at=datetime.now(UTC),
    )
    db.add(integration)
    _audit(
        db,
        request,
        workspace_id,
        actor.subject,
        "github_integration_added",
        "integration",
        integration.id,
        {"repository": repository},
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _problem(
            409, "github_integration_exists", "This repository is already registered."
        ) from None
    return {
        "id": integration.id,
        "provider": "github",
        "repository": repository,
        "incident_key": incident_key,
        "enabled": True,
    }


@router.post("/workspaces/{workspace_id}/integrations/github/webhook")
async def receive_github_deployment(
    workspace_id: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    signature: str = Header(default="", alias="X-Hub-Signature-256"),
    delivery_id: str = Header(default="", alias="X-GitHub-Delivery"),
    event_name: str = Header(default="", alias="X-GitHub-Event"),
) -> dict[str, Any]:
    raw = await request.body()
    if len(raw) > min(settings.pilot_max_payload_bytes, MAX_BODY_BYTES):
        raise _problem(
            413, "webhook_too_large", "The GitHub event exceeds the configured size limit."
        )
    if event_name != "deployment_status" or not delivery_id or len(delivery_id) > 160:
        raise _problem(
            400, "unsupported_github_event", "Only deployment_status webhook events are accepted."
        )
    try:
        body = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise _problem(
            400, "invalid_github_payload", "The GitHub webhook body must be JSON."
        ) from None
    if not isinstance(body, dict):
        raise _problem(400, "invalid_github_payload", "The GitHub webhook body must be an object.")
    repository_record = body.get("repository")
    repository = (
        str(repository_record.get("full_name", "")).lower()
        if isinstance(repository_record, dict)
        else ""
    )
    secret = settings.github_webhook_secrets.get(repository)
    if not secret:
        raise _problem(
            401, "github_repository_unconfigured", "The repository webhook is not configured."
        )
    supplied_signature = signature.removeprefix("sha256=")
    expected = hmac.new(secret.get_secret_value().encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied_signature, expected):
        raise _problem(
            401, "invalid_github_signature", "The GitHub webhook signature did not match."
        )
    _consume_rate_event(
        db,
        f"github:{repository}",
        "pilot_webhook",
        settings.pilot_webhook_requests_per_minute,
        datetime.now(UTC),
    )
    integration = db.scalar(
        select(PilotIntegration).where(
            PilotIntegration.workspace_id == workspace_id,
            PilotIntegration.provider == "github",
            PilotIntegration.external_id == repository,
            PilotIntegration.enabled.is_(True),
        )
    )
    if integration is None:
        raise _problem(
            404,
            "github_integration_not_found",
            "The repository is not connected to this workspace.",
        )
    incident = db.scalar(
        select(PilotIncident).where(
            PilotIncident.workspace_id == workspace_id,
            PilotIncident.incident_key == integration.incident_key,
        )
    )
    status = body.get("deployment_status") or {}
    deployment = body.get("deployment") or {}
    if not isinstance(status, dict) or not isinstance(deployment, dict):
        raise _problem(
            422, "incomplete_github_event", "The deployment status fields must be objects."
        )
    if incident is None or not deployment.get("id") or not status.get("state"):
        raise _problem(
            422,
            "incomplete_github_event",
            "The deployment event is missing its incident mapping or deployment status.",
        )
    deployment_id = str(deployment["id"])
    state = str(status["state"])
    if not deployment_id.isdecimal() or len(deployment_id) > 40:
        raise _problem(
            422, "invalid_github_deployment_id", "The deployment identifier is invalid."
        )
    if state not in {"queued", "in_progress", "inactive", "success", "failure", "error"}:
        raise _problem(
            422, "invalid_github_deployment_state", "The deployment status is unsupported."
        )
    service = db.scalar(
        select(PilotService).where(
            PilotService.workspace_id == workspace_id,
            PilotService.id == incident.primary_service_id,
        )
    )
    raw_time = (
        status.get("updated_at") or deployment.get("updated_at") or datetime.now(UTC).isoformat()
    )
    try:
        occurred_at = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=UTC)
    except ValueError:
        raise _problem(
            422, "invalid_github_event_time", "The deployment timestamp is invalid."
        ) from None
    now = datetime.now(UTC)
    if occurred_at > now + timedelta(minutes=5) or occurred_at < now - timedelta(
        days=settings.pilot_retention_days
    ):
        raise _problem(
            422,
            "github_event_outside_retention",
            "The deployment timestamp is outside the accepted time window.",
        )
    late_arrival = occurred_at < now - timedelta(minutes=15)
    source_record_id = f"github:deployment:{deployment_id}:status:{state}"
    event_id = _evidence_id(workspace_id, "github", source_record_id)
    title = _clean_text(
        f"Deployment {state} · {deployment.get('environment') or 'unknown environment'}",
        240,
    )
    description = str(status.get("description") or deployment.get("description") or "")
    exercise_fixture = any(
        str(value or "").lower().startswith("synthetic checkout latency exercise")
        for value in (status.get("description"), deployment.get("description"))
    )
    payload = {
        "title": title,
        "summary": _clean_text(description or "GitHub deployment status event"),
        "repository": repository,
        "deployment_id": deployment_id,
        "commit_sha": _clean_text(str(deployment.get("sha") or ""), 80),
        "environment": _clean_text(str(deployment.get("environment") or "unknown"), 80),
        "state": state,
        "delivery_id": delivery_id,
        "late_arrival": late_arrival,
        "integration_source": "exercise_fixture" if exercise_fixture else "github_webhook",
    }
    prior_evidence_id = db.scalar(
        select(PilotEvidence.id).where(
            PilotEvidence.workspace_id == workspace_id,
            PilotEvidence.source == "github",
            PilotEvidence.source_record_id == source_record_id,
        )
    )
    if prior_evidence_id is not None:
        duplicate = True
    else:
        result = db.execute(
            insert(PilotEvidence)
            .values(
                id=event_id,
                workspace_id=workspace_id,
                incident_id=incident.id,
                service_id=service.id if service else incident.primary_service_id,
                kind="deploy",
                source="github",
                source_record_id=source_record_id,
                occurred_at=occurred_at,
                payload=payload,
                created_at=now,
                expires_at=now + timedelta(days=settings.pilot_retention_days),
            )
            .on_conflict_do_nothing(constraint="uq_pilot_evidence_dedupe")
        )
        duplicate = not result.rowcount
    _audit(
        db,
        request,
        workspace_id,
        "github:webhook",
        "github_deployment_received",
        "incident",
        incident.id,
        {"delivery_id": delivery_id, "deduplicated": duplicate},
    )
    db.commit()
    return {
        "accepted": not duplicate,
        "deduplicated": duplicate,
        "late_arrival": late_arrival,
        "incident_id": incident.id,
        "evidence_id": event_id,
    }
