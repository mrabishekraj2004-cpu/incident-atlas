from incident_atlas.evaluation import (
    evaluate_ai_rule_harness,
    evaluate_expanded_dataset,
    evaluate_fixture_dataset,
)


def test_base_evaluation_preserves_label_hash_and_improves_evidence_recall():
    result = evaluate_fixture_dataset()
    assert result["dataset_sha256"] == (
        "e17bdb3a56cc8d92f8e2ec52da580742fa0f920c7fb738d11557dd311d33af58"
    )
    assert result["metrics"]["top_1_accuracy"] == 1.0
    assert result["metrics"]["mean_expected_support_evidence_recall"] == 1.0


def test_expanded_dataset_has_positive_and_abstention_cases():
    result = evaluate_expanded_dataset()
    assert result["case_count"] == 13
    assert result["source_counts"] == {
        "authored_synthetic_base": 3,
        "authored_synthetic_independent": 3,
        "authored_synthetic_missing_signal": 1,
        "derived_synthetic_variant": 6,
    }
    assert result["labeled_case_count"] == 8
    assert result["abstention_case_count"] == 5
    assert result["metrics"]["labeled_top_1_accuracy"] == 1.0
    assert result["metrics"]["mean_expected_support_evidence_recall"] == 1.0
    assert result["metrics"]["abstention_accuracy"] == 1.0
    assert result["metrics"]["overall_decision_accuracy"] == 1.0


def test_independent_and_missing_signal_cases_are_not_derived_from_base_incidents():
    result = evaluate_expanded_dataset()
    independent = [
        case
        for case in result["cases"]
        if case["data_kind"]
        in {"authored_synthetic_independent", "authored_synthetic_missing_signal"}
    ]
    assert {case["incident_id"] for case in independent} == {
        "eval-fraud-consumer-lag-001",
        "eval-checkout-cpu-throttling-002",
        "eval-shipping-span-ambiguous-003",
        "eval-checkout-missing-deploy-004",
    }
    assert all(case["decision_correct"] for case in independent)
    assert all(case["expected_supporting_evidence_recall"] == 1 for case in independent[:2])


def test_rules_and_injected_ai_see_the_same_label_free_evidence_packet():
    captured_packets = []

    def fake_ai(packet):
        captured_packets.append(packet)
        return {
            "hypotheses": [
                {
                    "statement": "cache key mismatch",
                    "supporting_evidence_ids": ["not-in-the-evidence-packet"],
                    "contradicting_evidence_ids": [],
                }
            ],
            "usage": {"input_tokens": 100, "output_tokens": 20},
            "cost_usd": 0.01,
        }

    result = evaluate_ai_rule_harness(fake_ai)
    assert result["provider_status"] == "external_model_observed"
    assert result["same_evidence_for_rules_and_ai"] is True
    assert result["prompt_contains_evaluation_labels"] is False
    assert len(captured_packets) == result["case_count"]
    for packet, case in zip(captured_packets, result["rules_cases"], strict=True):
        serialized = str(packet)
        if case["expected_primary_label"]:
            assert case["expected_primary_label"] not in serialized
    assert all(
        rule_case["same_evidence_sha256"] == ai_case["same_evidence_sha256"]
        for rule_case, ai_case in zip(result["rules_cases"], result["model_cases"], strict=True)
    )
    assert result["model_metrics"]["citation_validity"] == 0.0
    assert result["model_metrics"]["unsupported_claim_count_proxy"] == result["case_count"]
    assert result["model_metrics"]["input_tokens"] == 100 * result["case_count"]
    assert result["model_metrics"]["cost_usd"] == 0.01 * result["case_count"]


def test_provider_pending_and_mock_harness_are_labeled_honestly():
    pending = evaluate_ai_rule_harness()
    assert pending["provider_status"] == "pending_live_provider"
    assert pending["model_metrics"] is None

    mock = evaluate_ai_rule_harness(mock_provider=True)
    assert mock["provider_status"] == "mock_harness_validation_only"
    assert mock["mock_results_are_performance_evidence"] is False
    assert mock["model_metrics"]["citation_validity"] == 1.0
    assert all(
        rule_case["same_evidence_sha256"] == ai_case["same_evidence_sha256"]
        for rule_case, ai_case in zip(mock["rules_cases"], mock["model_cases"], strict=True)
    )
