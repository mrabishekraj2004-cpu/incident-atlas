# Incident Atlas evaluation report

**Recorded:** 2026-11-27  
**Status:** deterministic synthetic regression passed locally; live AI comparison pending.  
**Scope:** rules baseline and evaluation-harness validation, not production incident accuracy.

## Method

`api/incident_atlas/evaluation.py` sends the same normalized evidence-only packet to the deterministic rules baseline and an optional adapter. Expected labels are retained in scorer-only dataset files and added only after the adapter returns. The scorer checks top-1 label, abstention, source citation validity, expected-support recall, an unsupported-claim proxy, per-case latency, provider failure type, token counts, and optional cost. The prompt packet is checked for expected labels. This set has not been independently reviewed by outside incident responders.

Dataset version: `expanded-synthetic-v1`  
Dataset SHA-256: `81954d9de144fcaca61d20bb38f6e2c228aabcd8a7bb33dbc7cd53ccb6990adf`

Authorship: all 13 cases attribute the Incident Atlas project team; individual authors were not recorded. The 3 separate synthetic scenarios are authored apart from the base fixtures, not external or blind cases. The case mix is 3 authored base, 6 derived variants, 3 separately authored synthetic scenarios, and 1 missing-signal scenario. Eight are positive labels and five require abstention.

## Observed rules baseline results

| Metric | Result |
|---|---:|
| Cases | 13 |
| Labeled top-1 accuracy (8 positive cases) | 8/8 (100%) |
| Overall decision accuracy | 13/13 (100%) |
| Mean reciprocal rank | 1.00 |
| Expected-support citation recall | 100% average on positive cases |
| Citation IDs valid against packet | 100% |
| Appropriate abstention (5 cases) | 5/5 (100%) |
| Unnecessary positive-case abstention | 0/8 |

These are observed deterministic results on the fixed synthetic regression set only. They do not estimate performance on real services, unseen causes, or participant workloads.

## AI adapter results

The command `uv run python -m incident_atlas.cli evaluate-ai-rules --mock-provider` completed successfully. Its provider status is `mock_harness_validation_only`; its adapter simply echoes rules output. It confirms shared evidence hashes, label-free input, citation parsing, abstention accounting, and error/cost fields. Its 100% label/citation/abstention scores are identical to the rules output by construction and are **not AI performance evidence**. The measured ~0.06 ms average mock adapter time is not model latency. Token counts and cost are zero/null because no provider was called.

Live AI output is pending: no live provider request was made, no external provider credential is configured, and no model cost or latency has been measured. There is no measured AI advantage to report.

## Engineering interpretation

The rules baseline is sufficient for the current known synthetic patterns (deployment/latency correlation, cache miss shift, pool pressure, upstream gateway symptoms, consumer lag, and CPU throttling) and it correctly abstains on the five test cases marked ambiguous or incomplete. The next potential AI value is not a higher score on a rules-echo mock. It must be demonstrated on new, independently authored and reviewed ambiguous cases with improved evidence ranking or useful abstention while maintaining citation validity and zero unsupported causal claims. That experiment remains unrun.

## Reproduction

From `api/`:

```bash
uv sync --locked --extra dev --extra observability
uv run python -m incident_atlas.cli evaluate-expanded
uv run python -m incident_atlas.cli evaluate-ai-rules
uv run python -m incident_atlas.cli evaluate-ai-rules --mock-provider
```

The first two commands score the rules and report that live provider evaluation is pending; the final command checks the harness with the non-performance mock. To save the detailed per-case evidence locally, redirect the output to a private path outside tracked repository files.
