from __future__ import annotations
from datetime import datetime, timezone

from app.parsers.base import ParsedMessage
from app.parsers.dedupe_messages import dedupe_parsed_in_batch


def test_dedupe_in_batch_keeps_last():
    t = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    a = ParsedMessage(message_time=t, name=" 甲 ", content="  hi  ")
    b = ParsedMessage(message_time=t, name="甲", content="hi")
    c = ParsedMessage(message_time=t, name="乙", content="x")
    out = dedupe_parsed_in_batch([a, b, c])
    assert len(out) == 2
    # a 与 b 键相同，保留后出现的 b
    keys = {(m.name.strip() or "unknown", m.content.strip()) for m in out}
    assert ("甲", "hi") in keys
    assert ("乙", "x") in keys
