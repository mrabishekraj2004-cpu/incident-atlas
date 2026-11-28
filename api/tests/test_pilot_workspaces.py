from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

pytestmark = pytest.mark.postgres


def _seed_pilot():
    from incident_atlas.db import SessionLocal
    from incident_atlas.pilot_cli import seed

    with SessionLocal() as db:
        seed(db)


def _headers(subject: str) -> dict[str, str]:
    return {"X-Atlas-Dev-User": subject}


def _metrics_request(*, service_name: str, timestamp: datetime, value: float):
    from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
        ExportMetricsServiceRequest,
    )

    request = ExportMetricsServiceRequest()
    group = request.resource_metrics.add()
    service = group.resource.attributes.add()
    service.key = "service.name"
    service.value.string_value = service_name
    metric = group.scope_metrics.add().metrics.add()
    metric.name = "checkout.request.duration"
    metric.unit = "ms"
    point = metric.gauge.data_points.add()
    point.time_unix_nano = int(timestamp.timestamp() * 1_000_000_000)
    point.as_double = value
    label = point.attributes.add()
    label.key = "http.route"
    label.value.string_value = "/checkout"
    return request


def _record(
    db, *, incident_id: str, evidence_id: str, kind: str, source: str, at: datetime, payload: dict
):
    from incident_atlas.models import PilotEvidence

    db.add(
        PilotEvidence(
            id=evidence_id,
            workspace_id="payments-team",
            incident_id=incident_id,
            service_id="checkout-service",
            kind=kind,
            source=source,
            source_record_id=evidence_id,
            occurred_at=at,
            payload=payload,
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
    )


def test_workspaces_and_incidents_are_hidden_across_memberships(pg_client: TestClient) -> None:
    from incident_atlas.db import SessionLocal
    from incident_atlas.models import PilotIncident

    _seed_pilot()
    with SessionLocal() as db:
        alpha_incident = db.scalar(
            select(PilotIncident).where(PilotIncident.workspace_id == "payments-team")
        )
        beta_incident = db.scalar(
            select(PilotIncident).where(PilotIncident.workspace_id == "platform-team")
        )
        assert alpha_incident and beta_incident
        alpha_id, beta_id = alpha_incident.id, beta_incident.id

    alpha = pg_client.get("/api/v1/pilot/workspaces", headers=_headers("pilot.payments.viewer"))
    assert alpha.status_code == 200
    assert [row["id"] for row in alpha.json()["items"]] == ["payments-team"]
    assert (
        pg_client.get(
            f"/api/v1/pilot/workspaces/platform-team/incidents/{beta_id}",
            headers=_headers("pilot.payments.viewer"),
        ).status_code
        == 404
    )
    assert (
        pg_client.get(
            f"/api/v1/incidents/{alpha_id}", headers=_headers("pilot.payments.viewer")
        ).status_code
        == 404
    )
    assert (
        pg_client.post(
            f"/api/v1/pilot/workspaces/payments-team/incidents/{alpha_id}/investigations",
            headers=_headers("pilot.payments.viewer"),
            json={},
        ).status_code
        == 403
    )


def test_role_change_is_audited_and_revocation_applies_on_next_request(
    pg_client: TestClient,
) -> None:
    from incident_atlas.db import SessionLocal
    from incident_atlas.models import PilotIncident

    _seed_pilot()
    with SessionLocal() as db:
        incident = db.scalar(
            select(PilotIncident).where(PilotIncident.workspace_id == "payments-team")
        )
        assert incident is not None
        incident_id = incident.id
        db.commit()

    updated = pg_client.put(
        "/api/v1/pilot/workspaces/payments-team/members/pilot.payments.editor",
        headers=_headers("pilot.payments.owner"),
        json={"role": "viewer"},
    )
    assert updated.status_code == 200
    denied = pg_client.post(
        f"/api/v1/pilot/workspaces/payments-team/incidents/{incident_id}/investigations",
        headers=_headers("pilot.payments.editor"),
        json={},
    )
    assert denied.status_code == 403
    audit = pg_client.get(
        "/api/v1/pilot/workspaces/payments-team/audit", headers=_headers("pilot.payments.owner")
    )
    assert audit.status_code == 200
    assert any(item["action"] == "member_role_changed" for item in audit.json()["items"])

    removed = pg_client.delete(
        "/api/v1/pilot/workspaces/payments-team/members/pilot.payments.editor",
        headers=_headers("pilot.payments.owner"),
    )
    assert removed.status_code == 204
    assert (
        pg_client.get(
            "/api/v1/pilot/workspaces/payments-team/incidents",
            headers=_headers("pilot.payments.editor"),
        ).status_code
        == 404
    )
    audit = pg_client.get(
        "/api/v1/pilot/workspaces/payments-team/audit",
        headers=_headers("pilot.payments.owner"),
    )
    assert any(item["action"] == "member_removed" for item in audit.json()["items"])

    no_owner = pg_client.put(
        "/api/v1/pilot/workspaces/payments-team/members/pilot.payments.owner",
        headers=_headers("pilot.payments.owner"),
        json={"role": "viewer"},
    )
    assert no_owner.status_code == 409


def test_citations_resolve_to_immutable_evidence_captured_at_investigation_time(
    pg_client: TestClient,
) -> None:
    from incident_atlas.db import SessionLocal
    from incident_atlas.models import PilotEvidence, PilotIncident

    _seed_pilot()
    now = datetime.now(UTC)
    with SessionLocal() as db:
        incident = db.scalar(
            select(PilotIncident).where(PilotIncident.workspace_id == "payments-team")
        )
        assert incident is not None
        incident_id = incident.id
        _record(
            db,
            incident_id=incident_id,
            evidence_id="deploy-one",
            kind="deploy",
            source="github",
            at=now,
            payload={"title": "Deployment succeeded", "summary": "Change deployed."},
        )
        _record(
            db,
            incident_id=incident_id,
            evidence_id="metric-before",
            kind="metric",
            source="otel",
            at=now - timedelta(seconds=1),
            payload={"metric_name": "checkout.request.duration", "value": 30, "unit": "ms"},
        )
        _record(
            db,
            incident_id=incident_id,
            evidence_id="metric-after",
            kind="metric",
            source="otel",
            at=now + timedelta(seconds=1),
            payload={"metric_name": "checkout.request.duration", "value": 180, "unit": "ms"},
        )
        _record(
            db,
            incident_id=incident_id,
            evidence_id="trace-after",
            kind="trace",
            source="otel",
            at=now + timedelta(seconds=2),
            payload={"operation": "GET /checkout", "duration_ms": 180},
        )
        db.commit()

    response = pg_client.post(
        f"/api/v1/pilot/workspaces/payments-team/incidents/{incident_id}/investigations",
        headers=_headers("pilot.payments.editor"),
        json={},
    )
    assert response.status_code == 201
    report = response.json()
    assert report["source"] == "rules_fresh_analysis"
    assert report["model_call_made"] is False
    assert report["hypotheses"]
    assert "deploy-one" in report["hypotheses"][0]["supporting_evidence_ids"]
    evidence_url = (
        "/api/v1/pilot/workspaces/payments-team/snapshots/"
        f"{report['evidence_snapshot_id']}/evidence/metric-after"
    )
    captured = pg_client.get(evidence_url, headers=_headers("pilot.payments.viewer"))
    assert captured.status_code == 200
    original_sha = captured.json()["snapshot_sha256"]
    assert captured.json()["payload"]["value"] == 180
    with SessionLocal() as db:
        record = db.get(PilotEvidence, "metric-after")
        assert record is not None
        record.payload = {"metric_name": "checkout.request.duration", "value": 1, "unit": "ms"}
        db.commit()

    after = pg_client.get(evidence_url, headers=_headers("pilot.payments.viewer"))
    assert after.status_code == 200
    assert after.json()["payload"]["value"] == 180
    assert after.json()["snapshot_sha256"] == original_sha
    cross_workspace = pg_client.get(
        f"/api/v1/pilot/workspaces/platform-team/snapshots/{report['evidence_snapshot_id']}/evidence/metric-after",
        headers=_headers("pilot.platform.viewer"),
    )
    assert cross_workspace.status_code == 404


def test_expired_evidence_reports_and_snapshot_citations_are_hidden(
    pg_client: TestClient,
) -> None:
    from incident_atlas.db import SessionLocal
    from incident_atlas.models import (
        PilotEvidence,
        PilotIncident,
        PilotReport,
        PilotSnapshot,
    )

    _seed_pilot()
    now = datetime.now(UTC)
    with SessionLocal() as db:
        incident = db.scalar(
            select(PilotIncident).where(PilotIncident.workspace_id == "payments-team")
        )
        assert incident is not None
        incident_id = incident.id
        _record(
            db,
            incident_id=incident_id,
            evidence_id="expired-evidence",
            kind="log",
            source="otel",
            at=now - timedelta(days=31),
            payload={"message": "Expired synthetic record"},
        )
        expired = db.get(PilotEvidence, "expired-evidence")
        assert expired is not None
        expired.expires_at = now - timedelta(seconds=1)
        _record(
            db,
            incident_id=incident_id,
            evidence_id="retained-deployment",
            kind="deploy",
            source="github",
            at=now,
            payload={"title": "Deployment succeeded", "summary": "Synthetic exercise."},
        )
        db.commit()

    incident_response = pg_client.get(
        f"/api/v1/pilot/workspaces/payments-team/incidents/{incident_id}",
        headers=_headers("pilot.payments.viewer"),
    )
    assert incident_response.status_code == 200
    assert incident_response.json()["signal_counts"] == {"deploy": 1}
    timeline = pg_client.get(
        f"/api/v1/pilot/workspaces/payments-team/incidents/{incident_id}/timeline",
        headers=_headers("pilot.payments.viewer"),
    )
    assert "expired-evidence" not in {row["evidence_id"] for row in timeline.json()["items"]}

    report_response = pg_client.post(
        f"/api/v1/pilot/workspaces/payments-team/incidents/{incident_id}/investigations",
        headers=_headers("pilot.payments.editor"),
        json={},
    )
    assert report_response.status_code == 201
    report = report_response.json()
    with SessionLocal() as db:
        saved_report = db.get(PilotReport, report["id"])
        snapshot = db.get(PilotSnapshot, report["evidence_snapshot_id"])
        assert saved_report is not None and snapshot is not None
        saved_report.expires_at = now - timedelta(seconds=1)
        snapshot.expires_at = now - timedelta(seconds=1)
        db.commit()

    report_url = f"/api/v1/pilot/workspaces/payments-team/reports/{report['id']}"
    assert pg_client.get(report_url, headers=_headers("pilot.payments.viewer")).status_code == 404
    listed = pg_client.get(
        f"/api/v1/pilot/workspaces/payments-team/incidents/{incident_id}/reports",
        headers=_headers("pilot.payments.viewer"),
    )
    assert listed.json()["items"] == []
    citation_url = (
        "/api/v1/pilot/workspaces/payments-team/snapshots/"
        f"{report['evidence_snapshot_id']}/evidence/retained-deployment"
    )
    assert pg_client.get(citation_url, headers=_headers("pilot.payments.viewer")).status_code == 404

def test_otlp_ingestion_is_bounded_retry_safe_partial_and_reports_late_data(
    pg_client: TestClient,
) -> None:
    from incident_atlas.db import SessionLocal
    from incident_atlas.models import PilotIncident
    from incident_atlas.pilot_cli import issue_token

    _seed_pilot()
    with SessionLocal() as db:
        incident = db.scalar(
            select(PilotIncident).where(PilotIncident.workspace_id == "payments-team")
        )
        assert incident is not None
        incident_id = incident.id
        token, _ = issue_token(db, "payments-team", "checkout-service")

    now = datetime.now(UTC)
    message = _metrics_request(
        service_name="checkout-service", timestamp=now - timedelta(minutes=20), value=31
    )
    message.MergeFrom(_metrics_request(service_name="unknown-service", timestamp=now, value=99))
    message.MergeFrom(
        _metrics_request(
            service_name="checkout-service", timestamp=now - timedelta(days=45), value=4
        )
    )
    body = message.SerializeToString()
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Atlas-Incident-Id": incident_id,
        "Idempotency-Key": "first-metric-batch",
    }
    first = pg_client.post("/api/v1/pilot/ingest/otel/v1/metrics", content=body, headers=headers)
    assert first.status_code == 200
    assert first.json() == {
        "signal": "metrics",
        "accepted": 1,
        "duplicates": 0,
        "rejected": 2,
        "idempotent_replay": False,
        "late_arrivals": 1,
    }

    retry = pg_client.post("/api/v1/pilot/ingest/otel/v1/metrics", content=body, headers=headers)
    assert retry.status_code == 200
    assert retry.json()["idempotent_replay"] is True
    assert retry.json()["accepted"] == 0
    assert retry.json()["duplicates"] == 1

    changed = _metrics_request(
        service_name="checkout-service", timestamp=now - timedelta(minutes=20), value=42
    )
    conflict = pg_client.post(
        "/api/v1/pilot/ingest/otel/v1/metrics", content=changed.SerializeToString(), headers=headers
    )
    assert conflict.status_code == 409

    replay_batch = pg_client.post(
        "/api/v1/pilot/ingest/otel/v1/metrics",
        content=changed.SerializeToString(),
        headers={**headers, "Idempotency-Key": "same-record-new-batch"},
    )
    assert replay_batch.status_code == 200
    assert replay_batch.json()["accepted"] == 0
    assert replay_batch.json()["duplicates"] == 1

    incident_response = pg_client.get(
        f"/api/v1/pilot/workspaces/payments-team/incidents/{incident_id}",
        headers=_headers("pilot.payments.viewer"),
    )
    assert incident_response.status_code == 200
    assert incident_response.json()["missing_signals"] == ["log", "trace", "deploy"]

    oversized = pg_client.post(
        "/api/v1/pilot/ingest/otel/v1/metrics",
        content=b"x" * 65_537,
        headers={"Authorization": f"Bearer {token}", "X-Atlas-Incident-Id": incident_id},
    )
    assert oversized.status_code == 413


def test_github_webhook_signature_delivery_dedup_and_workspace_scope(pg_client: TestClient) -> None:
    from incident_atlas.config import Settings, get_settings
    from incident_atlas.db import SessionLocal
    from incident_atlas.main import app
    from incident_atlas.models import PilotEvidence

    _seed_pilot()
    secret = "test-github-webhook-secret-that-is-long-enough"
    previous = app.dependency_overrides[get_settings]
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="test",
        database_url="postgresql+psycopg://test:test@localhost:5432/test",
        pilot_enabled=True,
        pilot_dev_auth_enabled=True,
        github_webhook_secrets={"incident-atlas-demo/checkout-service": secret},
    )
    payload = {
        "repository": {"full_name": "incident-atlas-demo/checkout-service"},
        "deployment": {
            "id": 81001,
            "sha": "a" * 40,
            "environment": "pilot",
            "description": "Synthetic checkout latency exercise deployment",
        },
        "deployment_status": {
            "state": "success",
            "description": "Synthetic exercise event.",
            "updated_at": datetime.now(UTC).isoformat(),
        },
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    url = "/api/v1/pilot/workspaces/payments-team/integrations/github/webhook"
    headers = {
        "X-GitHub-Event": "deployment_status",
        "X-GitHub-Delivery": "delivery-1",
        "X-Hub-Signature-256": signature,
    }
    try:
        first = pg_client.post(url, content=body, headers=headers)
        assert first.status_code == 200
        assert first.json()["accepted"] is True
        replay = pg_client.post(
            url, content=body, headers={**headers, "X-GitHub-Delivery": "delivery-2"}
        )
        assert replay.status_code == 200
        assert replay.json()["deduplicated"] is True

        late_payload = json.loads(body)
        late_payload["deployment"]["id"] = 81002
        late_payload["deployment_status"]["updated_at"] = (
            datetime.now(UTC) - timedelta(minutes=20)
        ).isoformat()
        late_raw = json.dumps(late_payload, separators=(",", ":")).encode()
        late_signature = "sha256=" + hmac.new(secret.encode(), late_raw, hashlib.sha256).hexdigest()
        late_event = pg_client.post(
            url,
            content=late_raw,
            headers={
                **headers,
                "X-GitHub-Delivery": "delivery-late",
                "X-Hub-Signature-256": late_signature,
            },
        )
        assert late_event.status_code == 200
        assert late_event.json()["late_arrival"] is True
        wrong_workspace = pg_client.post(
            "/api/v1/pilot/workspaces/platform-team/integrations/github/webhook",
            content=body,
            headers={**headers, "X-GitHub-Delivery": "delivery-3"},
        )
        assert wrong_workspace.status_code == 404
        bad_signature = pg_client.post(
            url, content=body, headers={**headers, "X-Hub-Signature-256": "sha256=" + "0" * 64}
        )
        assert bad_signature.status_code == 401
        with SessionLocal() as db:
            event = db.get(PilotEvidence, first.json()["evidence_id"])
            assert event is not None
            assert event.workspace_id == "payments-team"
            assert event.payload["integration_source"] == "exercise_fixture"
    finally:
        app.dependency_overrides[get_settings] = previous
