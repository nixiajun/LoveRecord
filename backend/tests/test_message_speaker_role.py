from app.services.ingest.message_pipeline import resolve_store_speaker_role


def test_resolve_owner_only():
    assert resolve_store_speaker_role("小明", {"小明"}, {"小红"}) == "owner"


def test_resolve_partner_only():
    assert resolve_store_speaker_role("小红", {"小明"}, {"小红"}) == "partner"


def test_resolve_ambiguous_unknown():
    assert resolve_store_speaker_role("路人", {"小明"}, {"小红"}) == "unknown"


def test_resolve_both_match_unknown():
    assert resolve_store_speaker_role("重名", {"重名", "a"}, {"重名", "b"}) == "unknown"
