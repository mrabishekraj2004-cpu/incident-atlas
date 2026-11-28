#!/usr/bin/env python3
"""Trigger a controlled checkout latency exercise and synthetic GitHub event."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime


def _request(url: str, *, method: str = "GET", payload: object | None = None, headers: dict[str, str] | None = None) -> object:
    body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Accept": "application/json", "Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            result = json.loads(response.read())
            if response.status >= 400:
                raise RuntimeError(f"request failed with HTTP {response.status}")
            return result
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"request failed with HTTP {exc.code}: {detail}") from None


def run(workspace: str, api_base: str, service_url: str) -> dict[str, object]:
    suffix = "ALPHA" if workspace == "payments-team" else "BRAVO"
    route = "/checkout" if workspace == "payments-team" else "/catalog"
    token = os.environ.get(f"PILOT_INGEST_TOKEN_{suffix}", "")
    incident_id = os.environ.get(f"PILOT_INCIDENT_ID_{suffix}", "")
    repository = os.environ.get(f"PILOT_REPOSITORY_{suffix}", "")
    webhook_secret = os.environ.get(f"PILOT_GITHUB_SECRET_{suffix}", "")
    if not all((token, incident_id, repository, webhook_secret)):
        raise SystemExit(f"Missing {suffix} values; source the local .env.pilot file first.")

    _request(f"{service_url}/__exercise/reset", method="POST", payload={})
    baseline = [
        _request(f"{service_url}{route}")
        for _ in range(4)
    ]
    flush_before = _request(f"{service_url}/__exercise/flush", method="POST", payload={})
    _request(f"{service_url}/__exercise/activate-regression", method="POST", payload={})

    now = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    deployment_id = int(time.time() * 1000)
    delivery_id = str(uuid.uuid4())
    webhook_payload = {
        "action": "created",
        "repository": {"full_name": repository},
        "deployment": {
            "id": deployment_id,
            "sha": hashlib.sha1(delivery_id.encode()).hexdigest(),
            "environment": "pilot-exercise",
            "description": "Synthetic checkout latency exercise deployment",
            "updated_at": now,
        },
        "deployment_status": {
            "state": "success",
            "description": "Synthetic exercise event; no GitHub account was contacted.",
            "updated_at": now,
        },
    }
    raw = json.dumps(webhook_payload, separators=(",", ":")).encode()
    signature = hmac.new(webhook_secret.encode(), raw, hashlib.sha256).hexdigest()
    webhook_result = _request(
        f"{api_base}/pilot/workspaces/{workspace}/integrations/github/webhook",
        method="POST",
        payload=webhook_payload,
        headers={
            "X-Hub-Signature-256": f"sha256={signature}",
            "X-GitHub-Delivery": delivery_id,
            "X-GitHub-Event": "deployment_status",
        },
    )
    regression = [_request(f"{service_url}{route}") for _ in range(6)]
    flush_after = _request(f"{service_url}/__exercise/flush", method="POST", payload={})

    return {
        "synthetic_exercise": True,
        "workspace": workspace,
        "scenario": "checkout latency after deploy" if workspace == "payments-team" else "catalog latency after deploy",
        "incident_id": incident_id,
        "baseline_requests": len(baseline),
        "post_deployment_requests": len(regression),
        "baseline_latency_ms": [item["latency_ms"] for item in baseline],
        "post_deployment_latency_ms": [item["latency_ms"] for item in regression],
        "deployment_event": webhook_result,
        "export_flush_before": flush_before,
        "export_flush_after": flush_after,
        "next_step": f"Open http://localhost:5173/pilot?workspace={workspace} and investigate {incident_id}.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", choices=("payments-team", "platform-team"), required=True)
    parser.add_argument("--api-base", default=os.getenv("PILOT_API_BASE_URL", "http://127.0.0.1:8000/api/v1"))
    parser.add_argument("--service-url", default=os.getenv("PILOT_SERVICE_URL", "http://127.0.0.1:8100"))
    args = parser.parse_args()
    print(json.dumps(run(args.workspace, args.api_base.rstrip("/"), args.service_url.rstrip("/")), indent=2))


if __name__ == "__main__":
    main()
