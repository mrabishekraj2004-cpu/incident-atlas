from incident_atlas.pilot import _clean_text, _evidence_id


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


def test_pilot_evidence_primary_keys_are_stable_and_workspace_scoped():
    first = _evidence_id("payments-team", "github", "deployment:42:success")
    retry = _evidence_id("payments-team", "github", "deployment:42:success")
    other_workspace = _evidence_id("platform-team", "github", "deployment:42:success")

    assert first == retry
    assert first != other_workspace
