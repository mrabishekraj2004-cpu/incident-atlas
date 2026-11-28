"""Offline-only evaluation helpers. Runtime API and live analysis never import this module."""

from copy import deepcopy
from pathlib import Path
from time import perf_counter
from typing import Any

from incident_atlas.fixtures import (
    LABELS_PATH,
    SCENARIOS_PATH,
    build_evidence_items,
    load_json,
    parse_dt,
    sha256_json,
)
from incident_atlas.rules import evaluate_rules

RULE_TO_LABEL = {
    "cache-miss-after-deploy": "cache_key_version_mismatch",
    "pool-saturation-with-stable-query": "inventory_connection_leak",
    "slow-downstream-with-retries": "upstream_payment_gateway_latency",
    "queue-consumer-lag-with-throughput-gap": "fraud_consumer_lag",
    "checkout-cpu-throttling-with-latency-rise": "checkout_cpu_throttling",
}
EVALUATION_DIR = Path(__file__).resolve().parents[2] / "data" / "evaluation"
VARIANTS_PATH = EVALUATION_DIR / "variants.json"
INDEPENDENT_CASES_PATH = EVALUATION_DIR / "independent-cases-v1.json"


def evaluate_fixture_dataset() -> dict[str, Any]:
    scenarios_payload = load_json(SCENARIOS_PATH)
    labels_payload = load_json(LABELS_PATH)
    labels = {case["incident_id"]: case for case in labels_payload["cases"]}
    outcomes: list[dict[str, Any]] = []
    reciprocal_ranks: list[float] = []
    evidence_recalls: list[float] = []

    for scenario in scenarios_payload["scenarios"]:
        label = labels[scenario["id"]]
        items = build_evidence_items(scenario)
        result = evaluate_rules(scenario["id"], parse_dt(scenario["started_at"]), items)
        predicted = [
            RULE_TO_LABEL[rule["rule_id"]]
            for rule in result["fired_rules"]
            if rule["rule_id"] in RULE_TO_LABEL
        ]
        expected = label["expected_primary_label"]
        rank = predicted.index(expected) + 1 if expected in predicted else None
        reciprocal_ranks.append(1 / rank if rank else 0.0)
        cited_ids = {
            evidence_id for rule in result["fired_rules"] for evidence_id in rule["evidence_ids"]
        }
        expected_support = set(label["expected_supporting_evidence_ids"])
        recall = (
            len(cited_ids & expected_support) / len(expected_support) if expected_support else 1.0
        )
        evidence_recalls.append(recall)
        outcomes.append(
            {
                "case_id": label["case_id"],
                "incident_id": scenario["id"],
                "data_kind": "authored_synthetic_base",
                "expected_primary_label": expected,
                "predicted_ranked_labels": predicted,
                "top_1_correct": bool(predicted and predicted[0] == expected),
                "reciprocal_rank": rank and 1 / rank or 0.0,
                "fired_rule_ids": [rule["rule_id"] for rule in result["fired_rules"]],
                "cited_evidence_ids": sorted(cited_ids),
                "expected_supporting_evidence_recall": round(recall, 4),
                "abstained": not bool(predicted),
            }
        )

    count = len(outcomes)
    correct = sum(outcome["top_1_correct"] for outcome in outcomes)
    return {
        "dataset_version": labels_payload["label_version"],
        "dataset_sha256": sha256_json(labels_payload),
        "fixture_version": scenarios_payload["fixture_version"],
        "case_count": count,
        "metrics": {
            "top_1_accuracy": round(correct / count, 4) if count else 0.0,
            "mean_reciprocal_rank": round(sum(reciprocal_ranks) / count, 4) if count else 0.0,
            "mean_expected_support_evidence_recall": round(sum(evidence_recalls) / count, 4)
            if count
            else 0.0,
            "abstention_rate": round(sum(outcome["abstained"] for outcome in outcomes) / count, 4)
            if count
            else 0.0,
        },
        "cases": outcomes,
    }


def _apply_variant(scenario: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    variant = deepcopy(scenario)
    for change in case["metric_changes"]:
        series = next(
            item for item in variant["metrics"] if item["metric_name"] == change["metric_name"]
        )
        series["values"][change["index"]] = change["value"]
    removed = set(case["remove_timeline_ids"])
    variant["timeline"] = [item for item in variant["timeline"] if item["id"] not in removed]
    return variant


def _independent_items(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items = deepcopy(evidence)
    for item in items:
        item["observed_at"] = parse_dt(item["observed_at"])
    return items


def evaluate_expanded_dataset() -> dict[str, Any]:
    """Evaluate base cases, derived variants, and separate authored cases."""
    scenarios_payload = load_json(SCENARIOS_PATH)
    base_labels_payload = load_json(LABELS_PATH)
    variants_payload = load_json(VARIANTS_PATH)
    independent_payload = load_json(INDEPENDENT_CASES_PATH)
    scenarios = {scenario["id"]: scenario for scenario in scenarios_payload["scenarios"]}
    independent_evidence = independent_payload["evidence_by_case"]
    cases: list[tuple[dict[str, Any], str, Any, list[dict[str, Any]], str]] = []
    for label in base_labels_payload["cases"]:
        scenario = scenarios[label["incident_id"]]
        cases.append(
            (
                label,
                scenario["id"],
                parse_dt(scenario["started_at"]),
                build_evidence_items(scenario),
                "authored_synthetic_base",
            )
        )
    for label in variants_payload["cases"]:
        scenario = _apply_variant(scenarios[label["incident_id"]], label)
        cases.append(
            (
                label,
                scenario["id"],
                parse_dt(scenario["started_at"]),
                build_evidence_items(scenario),
                "derived_synthetic_variant",
            )
        )
    for label in independent_payload["cases"]:
        cases.append(
            (
                label,
                label["incident_id"],
                parse_dt(label["incident_start"]),
                _independent_items(independent_evidence[label["case_id"]]),
                label["data_kind"],
            )
        )

    outcomes: list[dict[str, Any]] = []
    reciprocal_ranks: list[float] = []
    evidence_recalls: list[float] = []
    decisions_correct = 0
    labeled_correct = 0
    abstention_cases = 0
    correct_abstentions = 0
    for label, incident_id, incident_start, items, data_kind in cases:
        result = evaluate_rules(incident_id, incident_start, items)
        predicted = [
            RULE_TO_LABEL[rule["rule_id"]]
            for rule in result["fired_rules"]
            if rule["rule_id"] in RULE_TO_LABEL
        ]
        expected = label["expected_primary_label"]
        expected_abstention = label["expected_abstention"]
        abstained = not bool(predicted)
        top_one = bool(expected and predicted and predicted[0] == expected)
        decision_correct = abstained if expected_abstention else top_one
        cited_ids = {
            evidence_id for rule in result["fired_rules"] for evidence_id in rule["evidence_ids"]
        }
        expected_support = set(label["expected_supporting_evidence_ids"])
        recall = (
            len(cited_ids & expected_support) / len(expected_support) if expected_support else None
        )
        if expected_abstention:
            abstention_cases += 1
            correct_abstentions += int(abstained)
        else:
            rank = predicted.index(expected) + 1 if expected in predicted else None
            reciprocal_ranks.append(1 / rank if rank else 0.0)
            evidence_recalls.append(recall or 0.0)
            labeled_correct += int(top_one)
        decisions_correct += int(decision_correct)
        outcomes.append(
            {
                "case_id": label["case_id"],
                "author": label.get("author", "unattributed"),
                "incident_id": incident_id,
                "data_kind": data_kind,
                "expected_primary_label": expected,
                "predicted_ranked_labels": predicted,
                "top_1_correct": top_one,
                "decision_correct": decision_correct,
                "expected_abstention": expected_abstention,
                "abstained": abstained,
                "fired_rule_ids": [rule["rule_id"] for rule in result["fired_rules"]],
                "cited_evidence_ids": sorted(cited_ids),
                "expected_supporting_evidence_recall": (
                    round(recall, 4) if recall is not None else None
                ),
                "notes": label["notes"],
            }
        )

    count = len(outcomes)
    source_counts = {
        data_kind: sum(outcome["data_kind"] == data_kind for outcome in outcomes)
        for data_kind in sorted({outcome["data_kind"] for outcome in outcomes})
    }
    dataset_version = (
        f"{variants_payload['dataset_version']}+{independent_payload['dataset_version']}"
    )
    return {
        "dataset_version": dataset_version,
        "dataset_sha256": sha256_json(
            {
                "scenarios": scenarios_payload,
                "base_labels": base_labels_payload,
                "variants": variants_payload,
                "independent_cases": independent_payload,
            }
        ),
        "fixture_version": scenarios_payload["fixture_version"],
        "case_count": count,
        "source_counts": source_counts,
        "labeled_case_count": len(reciprocal_ranks),
        "abstention_case_count": abstention_cases,
        "metrics": {
            "overall_decision_accuracy": round(decisions_correct / count, 4) if count else 0.0,
            "labeled_top_1_accuracy": round(labeled_correct / len(reciprocal_ranks), 4)
            if reciprocal_ranks
            else 0.0,
            "mean_reciprocal_rank": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 4)
            if reciprocal_ranks
            else 0.0,
            "mean_expected_support_evidence_recall": round(
                sum(evidence_recalls) / len(evidence_recalls), 4
            )
            if evidence_recalls
            else 0.0,
            "abstention_accuracy": round(correct_abstentions / abstention_cases, 4)
            if abstention_cases
            else 0.0,
        },
        "cases": outcomes,
    }


def _expanded_cases() -> list[tuple[dict[str, Any], str, Any, list[dict[str, Any]], str]]:
    scenarios_payload = load_json(SCENARIOS_PATH)
    base_labels_payload = load_json(LABELS_PATH)
    variants_payload = load_json(VARIANTS_PATH)
    independent_payload = load_json(INDEPENDENT_CASES_PATH)
    scenarios = {scenario["id"]: scenario for scenario in scenarios_payload["scenarios"]}
    cases: list[tuple[dict[str, Any], str, Any, list[dict[str, Any]], str]] = []
    for label in base_labels_payload["cases"]:
        scenario = scenarios[label["incident_id"]]
        cases.append(
            (
                label,
                scenario["id"],
                parse_dt(scenario["started_at"]),
                build_evidence_items(scenario),
                "authored_synthetic_base",
            )
        )
    for label in variants_payload["cases"]:
        scenario = _apply_variant(scenarios[label["incident_id"]], label)
        cases.append(
            (
                label,
                scenario["id"],
                parse_dt(scenario["started_at"]),
                build_evidence_items(scenario),
                "derived_synthetic_variant",
            )
        )
    for label in independent_payload["cases"]:
        cases.append(
            (
                label,
                label["incident_id"],
                parse_dt(label["incident_start"]),
                _independent_items(independent_payload["evidence_by_case"][label["case_id"]]),
                label["data_kind"],
            )
        )
    return cases


def _evaluation_packet(incident_start: Any, items: list[dict[str, Any]]) -> dict[str, Any]:
    ordered_times = sorted(item["observed_at"] for item in items)
    evidence = [
        {
            "evidence_id": item["evidence_id"],
            "kind": item["kind"],
            "observed_at": item["observed_at"].isoformat().replace("+00:00", "Z")
            if getattr(item["observed_at"], "tzinfo", None)
            else str(item["observed_at"]),
            "payload": item["payload"],
        }
        for item in items
    ]
    return {
        "incident": {
            "title": "Synthetic incident evaluation",
            "severity": "SEV-2",
            "summary": "Use only the attached evidence to describe hypotheses or abstain.",
            "started_at": incident_start.isoformat().replace("+00:00", "Z"),
        },
        "window": {
            "start": ordered_times[0].isoformat().replace("+00:00", "Z") if ordered_times else None,
            "end": ordered_times[-1].isoformat().replace("+00:00", "Z") if ordered_times else None,
        },
        "services": [],
        "dependencies": [],
        "evidence": evidence,
    }


def _mock_ai_from_rules(packet: dict[str, Any]) -> dict[str, Any]:
    """Harness fixture only: echo rule output to test parsing and scoring without a provider."""
    incident_start = parse_dt(packet["incident"]["started_at"])
    items = [{**item, "observed_at": parse_dt(item["observed_at"])} for item in packet["evidence"]]
    result = evaluate_rules("mock", incident_start, items)
    hypotheses = []
    for index, rule in enumerate(result["fired_rules"], start=1):
        hypotheses.append(
            {
                "rank": index,
                "statement": rule["label"],
                "supporting_evidence_ids": rule["evidence_ids"],
                "contradicting_evidence_ids": [],
            }
        )
    return {"hypotheses": hypotheses, "usage": None, "provider_request_id": None}


def _label_from_statement(statement: str) -> str | None:
    normalized = statement.lower().replace("_", " ")
    phrases = {
        "cache_key_version_mismatch": ("cache key", "cache version", "cache miss"),
        "inventory_connection_leak": ("connection leak", "pool saturation", "inventory pool"),
        "upstream_payment_gateway_latency": (
            "payment gateway",
            "gateway latency",
            "downstream gateway",
        ),
        "fraud_consumer_lag": ("consumer lag", "consumer backlog"),
        "checkout_cpu_throttling": ("cpu throttling", "cpu throttled"),
    }
    for label, aliases in phrases.items():
        if label.replace("_", " ") in normalized or any(alias in normalized for alias in aliases):
            return label
    return None


def evaluate_ai_rule_harness(ai_runner=None, *, mock_provider: bool = False) -> dict[str, Any]:
    """Score rules and an optional injected AI adapter on byte-identical evidence.

    The default has no provider call. ``mock_provider=True`` validates the scoring
    path with a transparent rules-echo fixture and must not be reported as model
    performance. Expected labels are used only after inference for scoring.
    """
    if mock_provider and ai_runner is not None:
        raise ValueError("choose either an injected provider or the mock fixture")
    runner = _mock_ai_from_rules if mock_provider else ai_runner
    cases = _expanded_cases()
    model_outcomes: list[dict[str, Any]] = []
    rule_outcomes: list[dict[str, Any]] = []
    for label, incident_id, incident_start, items, data_kind in cases:
        packet = _evaluation_packet(incident_start, items)
        evidence_digest = sha256_json(packet["evidence"])
        rules_result = evaluate_rules(incident_id, incident_start, items)
        rules_labels = [
            RULE_TO_LABEL[rule["rule_id"]]
            for rule in rules_result["fired_rules"]
            if rule["rule_id"] in RULE_TO_LABEL
        ]
        valid_evidence = {item["evidence_id"] for item in packet["evidence"]}
        rule_citations = [
            citation for rule in rules_result["fired_rules"] for citation in rule["evidence_ids"]
        ]
        expected_support = set(label["expected_supporting_evidence_ids"])
        rule_outcomes.append(
            {
                "case_id": label["case_id"],
                "author": label.get("author", "unattributed"),
                "data_kind": data_kind,
                "expected_primary_label": label["expected_primary_label"],
                "expected_abstention": bool(label["expected_abstention"]),
                "predicted_labels": rules_labels,
                "abstained": not rules_labels,
                "citation_ids": sorted(set(rule_citations)),
                "citation_valid": all(citation in valid_evidence for citation in rule_citations),
                "expected_support_recall": (
                    len(set(rule_citations) & expected_support) / len(expected_support)
                )
                if expected_support
                else None,
                "same_evidence_sha256": evidence_digest,
            }
        )
        if runner is None:
            continue
        started = perf_counter()
        provider_error = None
        try:
            ai_result = runner(packet)
        except Exception as exc:
            ai_result = {}
            provider_error = type(exc).__name__
        latency_ms = (perf_counter() - started) * 1000
        hypotheses = ai_result.get("hypotheses", []) if isinstance(ai_result, dict) else []
        if not isinstance(hypotheses, list):
            hypotheses = []
        citation_ids = [
            citation
            for hypothesis in hypotheses
            if isinstance(hypothesis, dict)
            for citation in hypothesis.get("supporting_evidence_ids", [])
            + hypothesis.get("contradicting_evidence_ids", [])
            if isinstance(citation, str)
        ]
        valid_citations = [citation for citation in citation_ids if citation in valid_evidence]
        ai_labels = [
            predicted
            for hypothesis in hypotheses
            if isinstance(hypothesis, dict)
            if (predicted := _label_from_statement(str(hypothesis.get("statement", ""))))
        ]
        unsupported = 0
        for hypothesis in hypotheses:
            if not isinstance(hypothesis, dict):
                unsupported += 1
                continue
            support = set(hypothesis.get("supporting_evidence_ids", []))
            if (
                label["expected_abstention"]
                or not support.intersection(valid_evidence)
                or (expected_support and not support.intersection(expected_support))
            ):
                unsupported += 1
        usage = ai_result.get("usage") if isinstance(ai_result, dict) else None
        if not isinstance(usage, dict):
            usage = {}
        model_outcomes.append(
            {
                "case_id": label["case_id"],
                "author": label.get("author", "unattributed"),
                "data_kind": data_kind,
                "expected_primary_label": label["expected_primary_label"],
                "expected_abstention": bool(label["expected_abstention"]),
                "predicted_labels": ai_labels,
                "abstained": not hypotheses,
                "appropriate_abstention": provider_error is None
                and (not hypotheses) == bool(label["expected_abstention"]),
                "provider_error_type": provider_error,
                "citation_ids": sorted(set(citation_ids)),
                "valid_citation_count": len(valid_citations),
                "citation_count": len(citation_ids),
                "citation_validity": (len(valid_citations) / len(citation_ids))
                if citation_ids
                else None,
                "unsupported_claim_count_proxy": unsupported,
                "expected_support_recall": (
                    len(set(citation_ids) & expected_support) / len(expected_support)
                )
                if expected_support
                else None,
                "latency_ms": round(latency_ms, 3),
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "cost_usd": ai_result.get("cost_usd") if isinstance(ai_result, dict) else None,
                "provider_request_id": ai_result.get("provider_request_id")
                if isinstance(ai_result, dict)
                else None,
                "same_evidence_sha256": evidence_digest,
            }
        )

    labeled = [row for row in rule_outcomes if not row["expected_abstention"]]
    abstention_cases = [row for row in rule_outcomes if row["expected_abstention"]]
    dataset_digest = sha256_json(
        {
            "scenarios": load_json(SCENARIOS_PATH),
            "base_labels": load_json(LABELS_PATH),
            "variants": load_json(VARIANTS_PATH),
            "independent_cases": load_json(INDEPENDENT_CASES_PATH),
        }
    )
    rules_metrics = {
        "labeled_top_1_accuracy": round(
            sum(
                bool(
                    row["predicted_labels"]
                    and row["predicted_labels"][0] == row["expected_primary_label"]
                )
                for row in labeled
            )
            / len(labeled),
            4,
        )
        if labeled
        else None,
        "appropriate_abstention_rate": round(
            sum(row["abstained"] for row in abstention_cases) / len(abstention_cases), 4
        )
        if abstention_cases
        else None,
        "positive_case_abstention_rate": round(
            sum(row["abstained"] for row in labeled) / len(labeled), 4
        )
        if labeled
        else None,
        "citation_validity": round(
            sum(row["citation_valid"] for row in rule_outcomes) / len(rule_outcomes), 4
        )
        if rule_outcomes
        else None,
        "mean_expected_support_recall": round(
            sum(row["expected_support_recall"] or 0 for row in labeled) / len(labeled), 4
        )
        if labeled
        else None,
    }
    model_metrics = None
    if runner is not None:
        non_abstain = [row for row in model_outcomes if not row["expected_abstention"]]
        abstain = [row for row in model_outcomes if row["expected_abstention"]]
        citations = sum(row["citation_count"] for row in model_outcomes)
        valid_citations = sum(row["valid_citation_count"] for row in model_outcomes)
        model_metrics = {
            "labeled_top_1_accuracy": round(
                sum(
                    bool(
                        row["predicted_labels"]
                        and row["predicted_labels"][0] == row["expected_primary_label"]
                    )
                    for row in non_abstain
                )
                / len(non_abstain),
                4,
            )
            if non_abstain
            else None,
            "appropriate_abstention_rate": round(
                sum(row["appropriate_abstention"] for row in abstain) / len(abstain), 4
            )
            if abstain
            else None,
            "positive_case_abstention_rate": round(
                sum(row["abstained"] for row in non_abstain) / len(non_abstain), 4
            )
            if non_abstain
            else None,
            "citation_validity": round(valid_citations / citations, 4) if citations else None,
            "unsupported_claim_count_proxy": sum(
                row["unsupported_claim_count_proxy"] for row in model_outcomes
            ),
            "provider_failure_count": sum(
                row["provider_error_type"] is not None for row in model_outcomes
            ),
            "mean_latency_ms": round(
                sum(row["latency_ms"] for row in model_outcomes) / len(model_outcomes), 3
            )
            if model_outcomes
            else None,
            "input_tokens": sum(row["input_tokens"] or 0 for row in model_outcomes),
            "output_tokens": sum(row["output_tokens"] or 0 for row in model_outcomes),
            "cost_usd": sum(
                row["cost_usd"]
                for row in model_outcomes
                if isinstance(row["cost_usd"], (int, float))
            )
            if any(isinstance(row["cost_usd"], (int, float)) for row in model_outcomes)
            else None,
        }
    return {
        "dataset_version": "expanded-synthetic-v1",
        "dataset_sha256": dataset_digest,
        "case_count": len(cases),
        "independent_authorship": (
            "Project team is attributed; individual authors are not recorded."
        ),
        "prompt_contains_evaluation_labels": False,
        "same_evidence_for_rules_and_ai": True,
        "provider_status": "mock_harness_validation_only"
        if mock_provider
        else "pending_live_provider"
        if runner is None
        else "external_model_observed",
        "mock_results_are_performance_evidence": False,
        "unsupported_claim_definition": (
            "Proxy: a claim is flagged when abstention is required, or cited support is missing, "
            "invalid, or has no overlap with labeled support. Human review is still required."
        ),
        "rules_metrics": rules_metrics,
        "model_metrics": model_metrics,
        "rules_cases": rule_outcomes,
        "model_cases": model_outcomes,
    }
