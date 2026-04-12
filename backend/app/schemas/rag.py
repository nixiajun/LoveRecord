"""混合召回 RAG：结构化意图、候选、请求/响应模式。"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class IntentType(str, Enum):
    fact_lookup = "fact_lookup"
    summary_request = "summary_request"
    quote_lookup = "quote_lookup"
    cause_analysis = "cause_analysis"
    timeline_lookup = "timeline_lookup"
    emotional_analysis = "emotional_analysis"


class DateMode(str, Enum):
    exact = "exact"
    relative = "relative"
    range = "range"
    none = "none"


class SpeakerRole(str, Enum):
    self = "self"
    partner = "partner"
    unknown = "unknown"


class StructuredQuery(BaseModel):
    """Query Understanding 输出。"""

    intent_type: IntentType = IntentType.fact_lookup
    date_mode: DateMode = DateMode.none
    day_key: Optional[str] = None
    date_range_start: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    date_range_end: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    speaker_role: SpeakerRole = SpeakerRole.unknown
    keywords: List[str] = Field(default_factory=list)
    message_types: List[str] = Field(
        default_factory=list,
        description="过滤 messages.type（如 image）",
    )
    chunk_source_types: List[str] = Field(
        default_factory=list,
        description="过滤 conversation_chunks.source_type",
    )
    needs_quote: bool = False
    needs_summary: bool = False
    needs_reasoning: bool = False
    sort_by_earliest: bool = False
    raw_question: str = ""

    class Config:
        use_enum_values = True


class CandidateSource(str, Enum):
    message = "message"
    chunk = "chunk"
    summary = "summary"


class RetrievalCandidate(BaseModel):
    """keyword / vector / summary 召回统一结构。"""

    source_type: CandidateSource
    source_ref_id: int
    day_key: str
    tool_name: Optional[str] = Field(
        default=None,
        description="产生该候选的 tool 名称，便于可解释 trace",
    )
    message_time: Optional[datetime] = None
    speaker_role: Optional[str] = None
    content: str = ""
    excerpt: str = ""
    keyword_score: float = 0.0
    vector_score: float = 0.0
    metadata_score: float = 0.0
    intent_score: float = 0.0
    total_score: float = 0.0
    extra: dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class CitationOut(BaseModel):
    """前端 / Bot 引用。"""

    source_type: str
    source_ref_id: int
    day_key: str
    chunk_id: Optional[int] = None
    message_id: Optional[int] = None
    excerpt: str = ""
    message_time: Optional[datetime] = None
    speaker_role: Optional[str] = None
    tool_name: Optional[str] = None


class ToolTraceEntry(BaseModel):
    """单次 tool 调用的可观测记录。"""

    tool_name: str
    input_summary: str = ""
    candidate_count: int = 0
    notes: List[str] = Field(default_factory=list)


class RagDebugInfo(BaseModel):
    router_path: str = ""
    candidate_count: int = 0
    selected_count: int = 0
    understanding_notes: List[str] = Field(default_factory=list)
    tool_trace: List[ToolTraceEntry] = Field(default_factory=list)
    selected_tools: List[str] = Field(default_factory=list)
    each_tool_candidate_count: dict[str, int] = Field(default_factory=dict)


class RagQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    include_debug: bool = False
    stream: bool = False
    channel: str = Field(default="web", max_length=64)
    """调用渠道（web/bot/api），仅用于观测。"""
    now_override: Optional[str] = Field(
        default=None,
        description="可选 YYYY-MM-DD，覆盖相对日期解析中的「今天」",
    )
    # 兼容旧客户端
    day_key: Optional[str] = None
    keyword: Optional[str] = None
    top_k: int = 12


class RagQueryResponse(BaseModel):
    question: str
    structured_query: StructuredQuery
    answer: str
    citations: List[dict[str, Any]]
    matched_day_keys: List[str] = Field(default_factory=list)
    tool_trace: List[ToolTraceEntry] = Field(default_factory=list)
    selected_tools: List[str] = Field(default_factory=list)
    debug: Optional[RagDebugInfo] = None


class RagDebugRetrieveResponse(BaseModel):
    structured_query: StructuredQuery
    candidates: List[RetrievalCandidate]
    router_path: str
    matched_day_keys: list[str] = Field(default_factory=list)
