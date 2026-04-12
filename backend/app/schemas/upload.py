from __future__ import annotations
from datetime import datetime

from pydantic import BaseModel


class UploadOut(BaseModel):
    id: int
    couple_id: int
    uploaded_by: int
    source_type: str
    original_filename: str
    file_path: str
    upload_date: str
    parse_status: str
    parse_error: str | None
    raw_text_excerpt: str | None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class UploadDetailOut(BaseModel):
    """单次上传详情（含解析状态、原文摘要、该次导入波及的日期与消息数）。"""

    id: int
    couple_id: int
    uploaded_by: int
    uploaded_by_display_name: str
    source_type: str
    original_filename: str
    file_path: str
    upload_date: str
    parse_status: str
    parse_error: str | None
    raw_text_excerpt: str | None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    message_count: int
    affected_day_keys: list[str]
