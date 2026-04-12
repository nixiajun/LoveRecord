from app.utils.query_classifier import (
    classify_chunk_source_filters,
    classify_intent,
    classify_message_type_filters,
    classify_speaker_hint,
)
from app.schemas.rag import IntentType, SpeakerRole


def test_classify_intent_summary_chat():
    intent, *_ = classify_intent("3月1日我们聊了什么")
    assert intent == IntentType.summary_request


def test_classify_message_image_filter():
    assert "image" in classify_message_type_filters("有没有发过猫的图片")


def test_classify_chunk_source_upload():
    assert classify_chunk_source_filters("导入的聊天记录里提到过上海") == ["upload_aggregate_day"]


def test_classify_speaker_partner():
    role, notes = classify_speaker_hint("她是不是生气了")
    assert role == SpeakerRole.partner
    assert "speaker:partner" in notes


def test_classify_speaker_reset_we():
    role, notes = classify_speaker_hint("我们上周为什么吵架")
    assert role == SpeakerRole.unknown
    assert "speaker:reset_we" in notes
