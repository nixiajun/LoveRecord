from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.parsers.base import ParserFieldMapping


class ParserOptionsIn(BaseModel):
    """上传 CSV/JSON 时可选的字段映射（表单 JSON 解析）。"""

    time_key: str | None = Field(default=None, description="时间列名或 JSON 键路径，如 sendTime 或 msg.time")
    speaker_key: str | None = Field(default=None, description="发言人列名或键路径")
    content_key: str | None = Field(default=None, description="正文列名或键路径")
    json_list_key: str | None = Field(
        default=None,
        description="仅 JSON：消息数组所在路径，如 messages、data.list；根为数组时可不填",
    )

    @model_validator(mode="after")
    def all_or_none_for_mapped_fields(self) -> ParserOptionsIn:
        keys = [self.time_key, self.speaker_key, self.content_key]
        stripped = [k.strip() if k else "" for k in keys]
        filled = sum(1 for k in stripped if k)
        if filled == 0:
            return self
        if filled != 3:
            raise ValueError("使用自定义映射时，时间、发言人、内容三个字段名都必须填写")
        return self

    def to_mapping(self) -> ParserFieldMapping | None:
        if not self.time_key or not self.speaker_key or not self.content_key:
            return None
        t = self.time_key.strip()
        s = self.speaker_key.strip()
        c = self.content_key.strip()
        if not t or not s or not c:
            return None
        lk = self.json_list_key.strip() if self.json_list_key else None
        return ParserFieldMapping(time_key=t, speaker_key=s, content_key=c, json_list_key=lk or None)
