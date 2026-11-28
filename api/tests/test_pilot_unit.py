from opentelemetry.proto.common.v1.common_pb2 import KeyValue

from incident_atlas.pilot import _clean_text, _evidence_id, _proto_attributes


def test_ingest_text_redacts_common_secret_and_personal_data_patterns():
    value = (
        "Bearer abcdefghijklmnopqrstuvwxyz password=hunter2 "
        "email=person@example.com card_number=4242 4242 4242 4242"
    )
    sanitized = _clean_text(value)
    assert "abcdefghijklmnop" not in sanitized
    assert "hunter2" not in sanitized
    assert "person@example.com" not in sanitized
    assert "4242" not in sanitized


def test_otlp_attribute_values_are_redacted_recursively():
    attributes = []
    message = KeyValue(key="exception.message")
    message.value.string_value = (
        "token=attribute-secret contact=person@example.com "
        "card_number=4242 4242 4242 4242"
    )
    attributes.append(message)

    authorization = KeyValue(key="http.request.header.authorization")
    authorization.value.string_value = "Bearer header-secret-value"
    attributes.append(authorization)

    nested = KeyValue(key="diagnostics")
    nested_value = nested.value.kvlist_value.values.add()
    nested_value.key = "detail"
    nested_value.value.string_value = "secret= nested-secret-value"
    nested_array = nested.value.kvlist_value.values.add()
    nested_array.key = "messages"
    nested_array.value.array_value.values.add().string_value = "contact=other@example.com"
    attributes.append(nested)

    sanitized = _proto_attributes(attributes)
    rendered = str(sanitized)

    assert "exception.message" in sanitized
    assert "diagnostics" in sanitized
    assert "attribute-secret" not in rendered
    assert "person@example.com" not in rendered
    assert "4242" not in rendered
    assert "authorization" not in rendered
    assert "header-secret-value" not in rendered
    assert "nested-secret-value" not in rendered
    assert "other@example.com" not in rendered


def test_pilot_evidence_primary_keys_are_stable_and_workspace_scoped():
    first = _evidence_id("payments-team", "github", "deployment:42:success")
    retry = _evidence_id("payments-team", "github", "deployment:42:success")
    other_workspace = _evidence_id("platform-team", "github", "deployment:42:success")

    assert first == retry
    assert first != other_workspace
