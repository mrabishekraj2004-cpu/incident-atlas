"""Additive workspace, ingestion, and immutable report storage for the pilot.

Revision ID: 0005_authenticated_pilot
Revises: 0004_bounded_rate_cleanup
Create Date: 2026-11-27
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_authenticated_pilot"
down_revision = "0004_bounded_rate_cleanup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pilot_workspaces",
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "pilot_memberships",
        sa.Column(
            "workspace_id",
            sa.String(120),
            sa.ForeignKey("pilot_workspaces.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("subject", sa.String(240), primary_key=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('owner','editor','viewer')", name="ck_pilot_membership_role"),
    )
    op.create_table(
        "pilot_services",
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(120),
            sa.ForeignKey("pilot_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("service_name", sa.String(160), nullable=False),
        sa.Column("owner_team", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "service_name", name="uq_pilot_service_workspace_name"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_pilot_service_workspace_id"),
    )
    op.create_table(
        "pilot_incidents",
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(120),
            sa.ForeignKey("pilot_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("incident_key", sa.String(160), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("primary_service_id", sa.String(120), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "incident_key", name="uq_pilot_incident_workspace_key"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_pilot_incident_workspace_id"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "primary_service_id"],
            ["pilot_services.workspace_id", "pilot_services.id"],
            name="fk_pilot_incident_primary_service_workspace",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "severity IN ('SEV-1','SEV-2','SEV-3','SEV-4')", name="ck_pilot_incident_severity"
        ),
        sa.CheckConstraint("status IN ('open','resolved')", name="ck_pilot_incident_status"),
    )
    op.create_table(
        "pilot_integrations",
        sa.Column("id", sa.String(180), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(120),
            sa.ForeignKey("pilot_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("external_id", sa.String(240), nullable=False),
        sa.Column("incident_key", sa.String(160), nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "external_id", name="uq_pilot_integration_provider_repo"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "incident_key"],
            ["pilot_incidents.workspace_id", "pilot_incidents.incident_key"],
            name="fk_pilot_integration_incident_workspace",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("provider = 'github'", name="ck_pilot_integration_provider"),
    )
    op.create_table(
        "pilot_ingest_tokens",
        sa.Column("id", sa.String(180), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(120),
            sa.ForeignKey("pilot_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("service_id", sa.String(120), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["workspace_id", "service_id"],
            ["pilot_services.workspace_id", "pilot_services.id"],
            name="fk_pilot_ingest_token_service_workspace",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_pilot_ingest_token_workspace", "pilot_ingest_tokens", ["workspace_id", "revoked_at"]
    )
    op.create_table(
        "pilot_evidence",
        sa.Column("id", sa.String(180), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(120),
            sa.ForeignKey("pilot_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "incident_id",
            sa.String(120),
            sa.ForeignKey("pilot_incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("service_id", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_record_id", sa.String(240), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "workspace_id", "source", "source_record_id", name="uq_pilot_evidence_dedupe"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "incident_id"],
            ["pilot_incidents.workspace_id", "pilot_incidents.id"],
            name="fk_pilot_evidence_incident_workspace",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "kind IN ('metric','log','trace','deploy')", name="ck_pilot_evidence_kind"
        ),
        sa.CheckConstraint(
            "source IN ('otel','github','synthetic_fixture')", name="ck_pilot_evidence_source"
        ),
    )
    op.create_index(
        "ix_pilot_evidence_workspace_incident_time",
        "pilot_evidence",
        ["workspace_id", "incident_id", "occurred_at"],
    )
    op.create_index("ix_pilot_evidence_expires", "pilot_evidence", ["expires_at"])
    op.create_table(
        "pilot_ingest_batches",
        sa.Column("id", sa.String(180), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(120),
            sa.ForeignKey("pilot_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("incident_id", sa.String(120), nullable=False),
        sa.Column("signal", sa.String(16), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("accepted_count", sa.Integer, nullable=False),
        sa.Column("duplicate_count", sa.Integer, nullable=False),
        sa.Column("rejected_count", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "workspace_id",
            "incident_id",
            "signal",
            "idempotency_key",
            name="uq_pilot_ingest_idempotency",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "incident_id"],
            ["pilot_incidents.workspace_id", "pilot_incidents.id"],
            name="fk_pilot_ingest_batch_incident_workspace",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_pilot_ingest_batch_created", "pilot_ingest_batches", ["created_at"])
    op.create_table(
        "pilot_snapshots",
        sa.Column("id", sa.String(180), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(120),
            sa.ForeignKey("pilot_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "incident_id",
            sa.String(120),
            sa.ForeignKey("pilot_incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("item_count", sa.Integer, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "id", name="uq_pilot_snapshot_workspace_id"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "incident_id"],
            ["pilot_incidents.workspace_id", "pilot_incidents.id"],
            name="fk_pilot_snapshot_incident_workspace",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_pilot_snapshot_expires", "pilot_snapshots", ["expires_at"])
    op.create_table(
        "pilot_snapshot_evidence",
        sa.Column(
            "snapshot_id",
            sa.String(180),
            sa.ForeignKey("pilot_snapshots.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("evidence_id", sa.String(180), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(120),
            sa.ForeignKey("pilot_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("service_id", sa.String(120), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "snapshot_id"],
            ["pilot_snapshots.workspace_id", "pilot_snapshots.id"],
            name="fk_pilot_snapshot_evidence_workspace",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_pilot_snapshot_evidence_workspace_lookup",
        "pilot_snapshot_evidence",
        ["workspace_id", "evidence_id"],
    )
    op.create_table(
        "pilot_reports",
        sa.Column("id", sa.String(180), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(120),
            sa.ForeignKey("pilot_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "incident_id",
            sa.String(120),
            sa.ForeignKey("pilot_incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_id",
            sa.String(180),
            sa.ForeignKey("pilot_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("report_payload", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "id", name="uq_pilot_report_workspace_id"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "incident_id"],
            ["pilot_incidents.workspace_id", "pilot_incidents.id"],
            name="fk_pilot_report_incident_workspace",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "snapshot_id"],
            ["pilot_snapshots.workspace_id", "pilot_snapshots.id"],
            name="fk_pilot_report_snapshot_workspace",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "source IN ('rules_fresh_analysis','stored_report')", name="ck_pilot_report_source"
        ),
    )
    op.create_index(
        "ix_pilot_report_workspace_incident",
        "pilot_reports",
        ["workspace_id", "incident_id", "created_at"],
    )
    op.create_index("ix_pilot_report_expires", "pilot_reports", ["expires_at"])
    op.create_table(
        "pilot_audit_events",
        sa.Column("id", sa.String(180), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(120),
            sa.ForeignKey("pilot_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subject", sa.String(240), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(180), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "attributes", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
    )
    op.create_index(
        "ix_pilot_audit_workspace_time", "pilot_audit_events", ["workspace_id", "occurred_at"]
    )


def downgrade() -> None:
    op.drop_table("pilot_audit_events")
    op.drop_table("pilot_reports")
    op.drop_table("pilot_snapshot_evidence")
    op.drop_table("pilot_snapshots")
    op.drop_table("pilot_ingest_batches")
    op.drop_table("pilot_evidence")
    op.drop_table("pilot_ingest_tokens")
    op.drop_table("pilot_integrations")
    op.drop_table("pilot_incidents")
    op.drop_table("pilot_services")
    op.drop_table("pilot_memberships")
    op.drop_table("pilot_workspaces")
