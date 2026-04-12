from __future__ import annotations
from datetime import datetime, timezone

from app.parsers.base import ParserFieldMapping
from app.parsers.csv_parser import CsvChatParser
from app.parsers.json_parser import JsonChatParser
from app.parsers.txt_parser import TxtChatParser


def test_txt_parser_basic():
    raw = "2026-04-01 10:00 小明：你好\n2026-04-01 10:01 小红：嗨"
    msgs = TxtChatParser().parse(raw, filename="x.txt")
    assert len(msgs) == 2
    assert msgs[0].name == "小明"


def test_txt_quoted_speaker_multiline():
    raw = "2026-04-01 00:00:25 '我'\n[图片]\n2026-04-01 00:01:00 '对方'\n你好"
    msgs = TxtChatParser().parse(raw, filename="x.txt")
    assert len(msgs) == 2
    assert msgs[0].name == "我"
    assert msgs[0].content == "[图片]"
    assert msgs[0].message_type == "image"
    assert msgs[1].name == "对方"
    assert msgs[1].content == "你好"


def test_csv_url_column_json_style():
    raw = (
        "time,speaker,content,emojiCdnUrl\n"
        "2026-04-01T10:00:00,甲,,https://cdn.example/z.png\n"
    )
    msgs = CsvChatParser().parse(raw, filename="x.csv")
    assert len(msgs) == 1
    assert msgs[0].url == "https://cdn.example/z.png"
    assert msgs[0].message_type == "image"


def test_csv_parser():
    raw = "time,speaker,content\n2026-04-01T10:00:00,小明,你好\n"
    msgs = CsvChatParser().parse(raw, filename="x.csv")
    assert len(msgs) == 1


def test_json_parser():
    raw = '[{"time":"2026-04-01T10:00:00+00:00","speaker":"小明","content":"hi"}]'
    msgs = JsonChatParser().parse(raw, filename="x.json")
    assert len(msgs) == 1


def test_csv_custom_column_names():
    raw = "发送时间,昵称,话\n2026-04-01T10:00:00,小明,你好\n"
    m = ParserFieldMapping(time_key="发送时间", speaker_key="昵称", content_key="话")
    msgs = CsvChatParser().parse(raw, filename="x.csv", field_mapping=m)
    assert len(msgs) == 1
    assert msgs[0].name == "小明"


def test_json_custom_keys_and_list_path():
    raw = '{"items":[{"ts":"2026-04-01T10:00:00+00:00","who":"小明","body":"hi"}]}'
    m = ParserFieldMapping(
        time_key="ts", speaker_key="who", content_key="body", json_list_key="items"
    )
    msgs = JsonChatParser().parse(raw, filename="x.json", field_mapping=m)
    assert len(msgs) == 1


def test_json_wechat_style_prefers_formatted_time():
    raw = """
    [{"localId":1,"createTime":1774972825,"formattedTime":"2026-04-01 00:00:25",
    "type":"图片消息","content":"[图片]","isSend":1,
    "senderUsername":"wxid_abc","senderDisplayName":"用户甲"}]
    """
    msgs = JsonChatParser().parse(raw, filename="x.json")
    assert len(msgs) == 1
    assert msgs[0].name == "用户甲"
    assert msgs[0].content == "[图片]"
    assert msgs[0].message_type == "image"
    # 优先 formattedTime，与导出界面日期一致（而非仅用 createTime 的 UTC 瞬时点）
    assert msgs[0].message_time.year == 2026
    assert msgs[0].message_time.month == 4
    assert msgs[0].message_time.day == 1
    assert msgs[0].message_time.hour == 0
    assert msgs[0].message_time.minute == 0
    assert msgs[0].message_time.second == 25


def test_json_wechat_animated_sticker_uses_emoji_cdn_url():
    raw = """
    [{"localId":7,"createTime":1774974249,"formattedTime":"2026-04-01 00:24:09",
    "type":"动画表情","localType":47,"content":"[表情包]","isSend":1,
    "senderDisplayName":"用户甲",
    "emojiCdnUrl":"https://example.com/sticker.gif"}]
    """
    msgs = JsonChatParser().parse(raw, filename="x.json")
    assert len(msgs) == 1
    assert msgs[0].content == "[表情包]"
    assert msgs[0].message_type == "image"
    assert msgs[0].url == "https://example.com/sticker.gif"


def test_json_nested_keys():
    raw = '[{"meta":{"at":"2026-04-01T10:00:00+00:00"},"sender":{"id":1,"name":"小明"},"text":"hi"}]'
    m = ParserFieldMapping(
        time_key="meta.at",
        speaker_key="sender.name",
        content_key="text",
    )
    msgs = JsonChatParser().parse(raw, filename="x.json", field_mapping=m)
    assert len(msgs) == 1
    assert msgs[0].name == "小明"


def test_timekey_helpers():
    from app.services.core.timekeys import to_day_key

    dt = datetime(2026, 4, 1, 15, 0, tzinfo=timezone.utc)
    assert to_day_key(dt, "Asia/Shanghai").startswith("2026-04-")
