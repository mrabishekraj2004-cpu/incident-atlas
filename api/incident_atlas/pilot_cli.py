"""Operator commands for provisioning and resetting the isolated workspace pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import shlex
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker

from incident_atlas.config import get_settings
from incident_atlas.database_urls import migration_database_url
from incident_atlas.models import (
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
    PilotWorkspace,
)

WORKSPACES = (
    {
        "id": "payments-team",
        "name": "Payments Team",
        "service_id": "checkout-service",
        "service_name": "checkout-service",
        "owner_team": "Payments",
        "incident_id": "payments-checkout-latency",
        "incident_key": "checkout-latency-regression",
        "repo": "incident-atlas-demo/checkout-service",
        "title": "Checkout latency regression after deploy",
    },
    {
        "id": "platform-team",
        "name": "Platform Team",
        "service_id": "catalog-service",
        "service_name": "catalog-service",
        "owner_team": "Platform",
        "incident_id": "platform-catalog-latency",
        "incident_key": "catalog-latency-regression",
        "repo": "incident-atlas-demo/catalog-service",
        "title": "Catalog latency regression after deploy",
    },
)
DEV_MEMBERS = (
    ("payments-team", "pilot.payments.owner", "owner"),
    ("payments-team", "pilot.payments.editor", "editor"),
    ("payments-team", "pilot.payments.viewer", "viewer"),
    ("platform-team", "pilot.platform.owner", "owner"),
    ("platform-team", "pilot.platform.editor", "editor"),
    ("platform-team", "pilot.platform.viewer", "viewer"),
)


def _session_factory() -> tuple[sessionmaker[Session], object]:
    settings = get_settings()
    url = migration_database_url(settings.database_url, settings.migration_database_url)
    engine = create_engine(url, pool_pre_ping=True)
    return sessionmaker(bind=engine, expire_on_commit=False), engine


def seed(session: Session) -> dict[str, int]:
    now = datetime.now(UTC)
    created = {"workspaces": 0, "services": 0, "incidents": 0, "integrations": 0, "memberships": 0}
    for data in WORKSPACES:
        workspace = session.get(PilotWorkspace, data["id"])
        if workspace is None:
            session.add(PilotWorkspace(id=data["id"], name=data["name"], created_at=now))
            created["workspaces"] += 1
        # This model has no ORM relationship mapping, so establish the parent
        # row before flushing the service foreign key.
        session.flush()
        service = session.get(PilotService, data["service_id"])
        if service is None:
            session.add(
                PilotService(
                    id=data["service_id"],
                    workspace_id=data["id"],
                    service_name=data["service_name"],
                    owner_team=data["owner_team"],
                    description="Synthetic sample service for the pilot exercise.",
                    created_at=now,
                )
            )
            created["services"] += 1
        # PostgreSQL checks the incident's composite workspace/service FK at
        # insert time; flush the service before adding its incident.
        session.flush()
        incident = session.scalar(
            select(PilotIncident).where(
                PilotIncident.workspace_id == data["id"],
                PilotIncident.incident_key == data["incident_key"],
            )
        )
        if incident is None:
            session.add(
                PilotIncident(
                    id=data["incident_id"],
                    workspace_id=data["id"],
                    incident_key=data["incident_key"],
                    title=data["title"],
                    severity="SEV-2",
                    summary=(
                        "Synthetic exercise: request latency rises after an application deployment."
                    ),
                    primary_service_id=data["service_id"],
                    started_at=now - timedelta(minutes=2),
                    status="open",
                    created_at=now,
                )
            )
            created["incidents"] += 1
        integration = session.scalar(
            select(PilotIntegration).where(
                PilotIntegration.provider == "github",
                PilotIntegration.external_id == data["repo"],
            )
        )
        if integration is None:
            session.add(
                PilotIntegration(
                    id=f"github_{data['id']}",
                    workspace_id=data["id"],
                    provider="github",
                    external_id=data["repo"],
                    incident_key=data["incident_key"],
                    enabled=True,
                    created_at=now,
                )
            )
            created["integrations"] += 1
    settings = get_settings()
    if settings.environment.lower() in {"development", "test"}:
        for workspace_id, subject, role in DEV_MEMBERS:
            existing = session.get(PilotMembership, (workspace_id, subject))
            if existing is None:
                session.add(
                    PilotMembership(
                        workspace_id=workspace_id, subject=subject, role=role, created_at=now
                    )
                )
                created["memberships"] += 1
    session.commit()
    return created


def issue_token(session: Session, workspace_id: str, service_id: str) -> tuple[str, datetime]:
    service = session.scalar(
        select(PilotService).where(
            PilotService.workspace_id == workspace_id, PilotService.id == service_id
        )
    )
    if service is None:
        raise SystemExit("service not found in the selected workspace")
    now = datetime.now(UTC)
    token = "ia_pilot_" + secrets.token_urlsafe(36)
    expires = now + timedelta(days=get_settings().pilot_ingest_token_ttl_days)
    session.add(
        PilotIngestToken(
            id=f"ingest_{uuid.uuid4().hex}",
            workspace_id=workspace_id,
            service_id=service_id,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            created_at=now,
            expires_at=expires,
        )
    )
    session.commit()
    return token, expires


def provision_member(session: Session, workspace_id: str, subject: str, role: str) -> None:
    if role not in {"owner", "editor", "viewer"}:
        raise SystemExit("role must be owner, editor, or viewer")
    if session.get(PilotWorkspace, workspace_id) is None:
        raise SystemExit("workspace not found")
    row = session.get(PilotMembership, (workspace_id, subject))
    now = datetime.now(UTC)
    if row is None:
        row = PilotMembership(workspace_id=workspace_id, subject=subject, role=role, created_at=now)
        session.add(row)
        action = "member_provisioned"
    else:
        if row.role == "owner" and role != "owner":
            owners = session.scalar(
                select(PilotMembership).where(
                    PilotMembership.workspace_id == workspace_id, PilotMembership.role == "owner"
                )
            )
            if owners is not None and owners.subject == subject:
                count = len(
                    session.scalars(
                        select(PilotMembership).where(
                            PilotMembership.workspace_id == workspace_id,
                            PilotMembership.role == "owner",
                        )
                    ).all()
                )
                if count <= 1:
                    raise SystemExit("cannot remove the last workspace owner")
        row.role = role
        action = "member_role_changed"
    session.add(
        PilotAuditEvent(
            id=f"audit_{uuid.uuid4().hex}",
            workspace_id=workspace_id,
            subject="system:provisioning",
            action=action,
            entity_type="membership",
            entity_id=subject,
            request_id="provisioning-cli",
            occurred_at=now,
            attributes={"role": role},
        )
    )
    session.commit()


def reset_incident(session: Session, workspace_id: str, incident_key: str) -> None:
    incident = session.scalar(
        select(PilotIncident).where(
            PilotIncident.workspace_id == workspace_id, PilotIncident.incident_key == incident_key
        )
    )
    if incident is None:
        raise SystemExit("incident not found in the selected workspace")
    now = datetime.now(UTC)
    session.execute(
        delete(PilotReport).where(
            PilotReport.workspace_id == workspace_id, PilotReport.incident_id == incident.id
        )
    )
    session.execute(
        delete(PilotSnapshot).where(
            PilotSnapshot.workspace_id == workspace_id, PilotSnapshot.incident_id == incident.id
        )
    )
    session.execute(
        delete(PilotEvidence).where(
            PilotEvidence.workspace_id == workspace_id, PilotEvidence.incident_id == incident.id
        )
    )
    session.execute(
        delete(PilotIngestBatch).where(
            PilotIngestBatch.workspace_id == workspace_id,
            PilotIngestBatch.incident_id == incident.id,
        )
    )
    incident.started_at = now - timedelta(minutes=2)
    session.add(
        PilotAuditEvent(
            id=f"audit_{uuid.uuid4().hex}",
            workspace_id=workspace_id,
            subject="system:exercise-reset",
            action="exercise_reset",
            entity_type="incident",
            entity_id=incident.id,
            request_id="pilot-cli-reset",
            occurred_at=now,
            attributes={"synthetic_fixture": True},
        )
    )
    session.commit()


def prune(session: Session) -> dict[str, int]:
    now = datetime.now(UTC)
    counts = {}
    # Reports are removed before snapshots due to their restrictive snapshot FK.
    for name, model in (
        ("reports", PilotReport),
        ("snapshots", PilotSnapshot),
        ("evidence", PilotEvidence),
        ("ingest_batches", PilotIngestBatch),
    ):
        result = session.execute(
            delete(model).where(model.expires_at < now)
            if hasattr(model, "expires_at")
            else delete(model).where(model.created_at < now - timedelta(days=30))
        )
        counts[name] = result.rowcount or 0
    counts["audit_events"] = (
        session.execute(
            delete(PilotAuditEvent).where(PilotAuditEvent.occurred_at < now - timedelta(days=365))
        ).rowcount
        or 0
    )
    counts["ingest_tokens"] = (
        session.execute(
            delete(PilotIngestToken).where(PilotIngestToken.expires_at < now - timedelta(days=365))
        ).rowcount
        or 0
    )
    session.commit()
    return counts


def write_local_env(session: Session, output: Path, force: bool) -> None:
    if output.exists() and not force:
        raise SystemExit(
            f"{output} already exists; move it aside or pass --force to rotate local tokens"
        )
    created = seed(session)
    settings = get_settings()
    if (
        not settings.pilot_enabled
        or settings.environment.lower() not in {"development", "test"}
        or not settings.pilot_dev_auth_enabled
    ):
        raise SystemExit(
            "bootstrap-local-env is available only with development identity mode enabled"
        )
    secrets_by_repo: dict[str, str] = {}
    variables = {
        "PILOT_API_BASE_URL": "http://127.0.0.1:8000/api/v1",
        "PILOT_SERVICE_URL": "http://127.0.0.1:8100",
        "PILOT_DEV_USER_ALPHA": "pilot.payments.editor",
        "PILOT_DEV_USER_BRAVO": "pilot.platform.editor",
    }
    for index, data in enumerate(WORKSPACES):
        if force:
            session.execute(
                delete(PilotIngestToken).where(
                    PilotIngestToken.workspace_id == data["id"],
                    PilotIngestToken.service_id == data["service_id"],
                )
            )
            session.commit()
        token, expires = issue_token(session, data["id"], data["service_id"])
        suffix = "ALPHA" if index == 0 else "BRAVO"
        secret = secrets.token_urlsafe(36)
        secrets_by_repo[data["repo"]] = secret
        variables[f"PILOT_INGEST_TOKEN_{suffix}"] = token
        variables[f"PILOT_INCIDENT_ID_{suffix}"] = data["incident_id"]
        variables[f"PILOT_WORKSPACE_ID_{suffix}"] = data["id"]
        variables[f"PILOT_SERVICE_NAME_{suffix}"] = data["service_name"]
        variables[f"PILOT_REPOSITORY_{suffix}"] = data["repo"]
        variables[f"PILOT_GITHUB_SECRET_{suffix}"] = secret
        variables[f"PILOT_TOKEN_EXPIRES_{suffix}"] = expires.isoformat()
    variables["PILOT_DEV_AUTH_ENABLED"] = "true"
    variables["GITHUB_WEBHOOK_SECRETS"] = json.dumps(secrets_by_repo, separators=(",", ":"))
    output.parent.mkdir(parents=True, exist_ok=True)
    contents = (
        "\n".join(f"export {key}={shlex.quote(value)}" for key, value in variables.items()) + "\n"
    )
    output.write_text(contents, encoding="utf-8")
    output.chmod(0o600)
    print(
        json.dumps(
            {
                "created": created,
                "environment_file": str(output),
                "permissions": "0600",
                "secret_values_printed": False,
            },
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="incident-atlas-pilot")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("seed", help="create the two synthetic sample workspaces")
    member = commands.add_parser(
        "provision-member", help="add or change an OIDC subject's workspace role"
    )
    member.add_argument("--workspace", required=True)
    member.add_argument("--subject", required=True)
    member.add_argument("--role", required=True, choices=("owner", "editor", "viewer"))
    token = commands.add_parser(
        "issue-token", help="create a one-time workspace-scoped telemetry token"
    )
    token.add_argument("--workspace", required=True)
    token.add_argument("--service", required=True)
    token.add_argument(
        "--stdout", action="store_true", help="print the token once; use a private terminal"
    )
    reset = commands.add_parser(
        "reset", help="clear exercise evidence and saved reports for one incident"
    )
    reset.add_argument("--workspace", required=True)
    reset.add_argument("--incident-key", required=True)
    local = commands.add_parser(
        "bootstrap-local-env", help="seed both teams and create a local secret file"
    )
    local.add_argument("--output", default=".env.pilot")
    local.add_argument(
        "--force",
        action="store_true",
        help="rotate local-only tokens and replace an existing output file",
    )
    commands.add_parser("prune", help="delete expired pilot evidence and audit records")
    args = parser.parse_args()
    factory, engine = _session_factory()
    try:
        with factory() as session:
            if args.command == "seed":
                result = seed(session)
                print(json.dumps(result, sort_keys=True))
            elif args.command == "provision-member":
                provision_member(session, args.workspace, args.subject, args.role)
                print(
                    json.dumps(
                        {"workspace": args.workspace, "subject": args.subject, "role": args.role}
                    )
                )
            elif args.command == "issue-token":
                value, expires = issue_token(session, args.workspace, args.service)
                if args.stdout:
                    print(value)
                else:
                    print(json.dumps({"token": value, "expires_at": expires.isoformat()}))
            elif args.command == "reset":
                reset_incident(session, args.workspace, args.incident_key)
                print(
                    json.dumps(
                        {
                            "workspace": args.workspace,
                            "incident_key": args.incident_key,
                            "reset": True,
                        }
                    )
                )
            elif args.command == "bootstrap-local-env":
                write_local_env(session, Path(args.output), args.force)
            elif args.command == "prune":
                print(json.dumps(prune(session), sort_keys=True))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
