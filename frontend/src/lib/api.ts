const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("lr_token");
}

export function setToken(t: string | null) {
  if (typeof window === "undefined") return;
  if (t) localStorage.setItem("lr_token", t);
  else localStorage.removeItem("lr_token");
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit & { auth?: boolean } = {}
): Promise<T> {
  const { auth = true, headers, ...rest } = init;
  const h = new Headers(headers);
  h.set("Content-Type", "application/json");
  if (auth) {
    const tok = getToken();
    if (tok) h.set("Authorization", `Bearer ${tok}`);
  }
  const r = await fetch(`${API_BASE}${path}`, { ...rest, headers: h });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(text || r.statusText);
  }
  if (r.status === 204) return undefined as T;
  return r.json() as Promise<T>;
}

export type RagStreamEvent =
  | { event: "meta"; question: string; structured_query: unknown; matched_day_keys: string[]; router_path?: string }
  | { event: "token"; text: string }
  | { event: "done"; citations: unknown[]; matched_day_keys: string[] };

// ─── 智能机器人：`POST /api/v1/smart-bot/chat` ───────────────────────────

export type SmartBotStreamEvent =
  | { event: "meta"; bot_name: string; skill: string; skill_label: string; question: string }
  | { event: "status"; message: string }
  | { event: "token"; text: string }
  | { event: "done"; skill_used: string; skill_label: string; citations: unknown[]; matched_day_keys: string[]; sql_query?: string; sql_row_count?: number };

export type SmartBotRequest = {
  question: string;
  stream?: boolean;
  identity?: { name: string; persona?: string } | null;
  now_override?: string | null;
  conversation_history?: { role: string; content: string }[];
};

/** POST /api/v1/smart-bot/chat，NDJSON 流式。 */
export async function smartBotStream(
  body: SmartBotRequest,
  onLine: (ev: SmartBotStreamEvent) => void
): Promise<void> {
  const h = new Headers();
  h.set("Content-Type", "application/json");
  const tok = getToken();
  if (tok) h.set("Authorization", `Bearer ${tok}`);
  const r = await fetch(`${API_BASE}/api/v1/smart-bot/chat`, {
    method: "POST",
    headers: h,
    body: JSON.stringify({ ...body, stream: true }),
  });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(text || r.statusText);
  }
  const reader = r.body?.getReader();
  if (!reader) throw new Error("无响应体");
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, i).trim();
      buf = buf.slice(i + 1);
      if (!line) continue;
      onLine(JSON.parse(line) as SmartBotStreamEvent);
    }
  }
}

// ─── 多 Agent 报表：`POST /api/v1/reports/*` ─────────────────────────────

export type ReportType = "daily" | "weekly" | "monthly";

/** 请求体：`/reports/daily|weekly|monthly/generate` */
export type ReportGenerateRequest = {
  /** 日报必填 YYYY-MM-DD */
  day_key?: string | null;
  /** 周/月报闭区间 YYYY-MM-DD */
  date_range_start?: string | null;
  date_range_end?: string | null;
  /** true 时响应带 `trace`（计划、findings、证据索引等） */
  include_debug?: boolean;
};

/** 调试：额外指定 `report_type` */
export type ReportDebugRequest = ReportGenerateRequest & {
  report_type?: ReportType;
};

export type ReportSubtask = {
  id: string;
  focus: string;
  date_range_start: string;
  date_range_end: string;
};

export type ReportPlan = {
  report_type: ReportType;
  date_range_start: string;
  date_range_end: string;
  couple_id: number;
  agents_pipeline: string[];
  retrieval_keywords: string[];
  subtasks: ReportSubtask[];
  planner_notes: string;
};

export type EvidenceRef = {
  ref_key: string;
  source_type: string;
  source_ref_id: number;
  day_key: string;
  excerpt: string;
  tool_name?: string | null;
};

export type AgentFinding = {
  agent_name: string;
  summary: string;
  bullet_points: string[];
  structured: Record<string, unknown>;
  low_evidence_notes: string[];
};

export type ReportBrief = {
  headline: string;
  overview: string;
  key_themes: string[];
  emotion_arc: string;
  highlights: string[];
  risks_or_friction: string[];
  memory_moments: string[];
  recommendations: string[];
  evidence_gaps: string[];
  extra: Record<string, unknown>;
};

/** 展示用正文：长文 + 微信短文 + 结构化小节（日报常用键见下方说明） */
export type FinalReport = {
  title: string;
  body_web: string;
  body_wechat: string;
  /** 常见键：overview, main_topics, warm_moments, friction_points, mood_tags, one_liner；editor_notes 等 */
  structured_sections: Record<string, unknown>;
};

export type ToolTraceEntry = {
  tool_name: string;
  input_summary: string;
  candidate_count: number;
  notes: string[];
};

/** 与 RAG CitationOut 一致，以服务端 JSON 为准 */
export type ReportCitation = {
  source_type: string;
  source_ref_id: number;
  day_key: string;
  chunk_id?: number | null;
  message_id?: number | null;
  excerpt: string;
  message_time?: string | null;
  speaker_role?: string | null;
  tool_name?: string | null;
};

export type ReportExecutionTrace = {
  report_type: ReportType;
  plan: ReportPlan | null;
  retrieval_trace: ToolTraceEntry[];
  evidence_refs: EvidenceRef[];
  findings: AgentFinding[];
  brief: ReportBrief | null;
  draft_before_edit: string;
  notes: string[];
};

/** `POST .../generate` 响应 */
export type ReportGenerateResponse = {
  report_type: ReportType;
  date_range_start: string;
  date_range_end: string;
  final: FinalReport;
  citations: ReportCitation[];
  trace?: ReportExecutionTrace | null;
};

export type ReportStreamRequest = {
  report_type: ReportType;
  day_key?: string | null;
  date_range_start?: string | null;
  date_range_end?: string | null;
  include_debug?: boolean;
};

export type ReportStreamEvent =
  | {
      event: "agent_phase";
      agent_key: string;
      agent_label_zh: string;
      status: "start" | "done";
      detail?: string;
    }
  | { event: "complete"; body: ReportGenerateResponse }
  | { event: "error"; message: string };

/** POST /api/v1/reports/stream/generate，NDJSON（可看各 Agent 中文阶段名） */
export type ReportJobOut = {
  id: number;
  couple_id: number;
  created_by_user_id: number;
  status: string;
  report_type: string;
  day_key: string | null;
  date_range_start: string;
  date_range_end: string;
  include_debug: boolean;
  error_message: string | null;
  current_agent: string | null;
  progress_pct: number | null;
  saved_report_id: number | null;
  created_at: string;
  updated_at: string;
};

/** 后台生成：202，立即返回任务；完成后见 GET /jobs/{id} 的 saved_report_id */
export async function enqueueReportJob(body: ReportStreamRequest): Promise<ReportJobOut> {
  return apiFetch<ReportJobOut>("/api/v1/reports/jobs", {
    method: "POST",
    body: JSON.stringify({
      report_type: body.report_type,
      day_key: body.day_key ?? null,
      date_range_start: body.date_range_start ?? null,
      date_range_end: body.date_range_end ?? null,
      include_debug: body.include_debug ?? false,
    }),
  });
}

export async function getReportJob(jobId: number): Promise<ReportJobOut> {
  return apiFetch<ReportJobOut>(`/api/v1/reports/jobs/${jobId}`);
}

export async function listReportJobs(limit = 30): Promise<ReportJobOut[]> {
  return apiFetch<ReportJobOut[]>(`/api/v1/reports/jobs?limit=${encodeURIComponent(String(limit))}`);
}

export async function streamReportGenerate(
  body: ReportStreamRequest,
  onEvent: (ev: ReportStreamEvent) => void
): Promise<void> {
  const h = new Headers();
  h.set("Content-Type", "application/json");
  const tok = getToken();
  if (tok) h.set("Authorization", `Bearer ${tok}`);
  const r = await fetch(`${API_BASE}/api/v1/reports/stream/generate`, {
    method: "POST",
    headers: h,
    body: JSON.stringify({
      report_type: body.report_type,
      day_key: body.day_key ?? null,
      date_range_start: body.date_range_start ?? null,
      date_range_end: body.date_range_end ?? null,
      include_debug: body.include_debug ?? false,
    }),
  });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(text || r.statusText);
  }
  const reader = r.body?.getReader();
  if (!reader) throw new Error("无响应体");
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, i).trim();
      buf = buf.slice(i + 1);
      if (!line) continue;
      const ev = JSON.parse(line) as ReportStreamEvent;
      onEvent(ev);
    }
  }
}

export type SavedReportListItem = {
  id: number;
  couple_id: number;
  report_type: string;
  date_range_start: string;
  date_range_end: string;
  title: string;
  created_at: string;
};

export type SavedReportDetailOut = SavedReportListItem & {
  body_web: string;
  body_wechat: string;
  structured_sections: Record<string, unknown> | unknown[] | null;
  citations: ReportCitation[] | Record<string, unknown> | null;
  trace: Record<string, unknown> | unknown[] | null;
  updated_at: string;
};

export async function archiveReport(payload: {
  report_type: ReportType;
  date_range_start: string;
  date_range_end: string;
  final: FinalReport;
  citations: ReportCitation[];
  trace?: ReportExecutionTrace | Record<string, unknown> | null;
}): Promise<SavedReportDetailOut> {
  return apiFetch<SavedReportDetailOut>("/api/v1/reports/archive", {
    method: "POST",
    body: JSON.stringify({
      report_type: payload.report_type,
      date_range_start: payload.date_range_start,
      date_range_end: payload.date_range_end,
      final: payload.final,
      citations: payload.citations,
      trace: payload.trace ?? null,
    }),
  });
}

export async function listArchivedReports(limit = 50): Promise<SavedReportListItem[]> {
  return apiFetch<SavedReportListItem[]>(`/api/v1/reports/archive?limit=${limit}`);
}

export async function getArchivedReport(id: number): Promise<SavedReportDetailOut> {
  return apiFetch<SavedReportDetailOut>(`/api/v1/reports/archive/${id}`);
}

export async function deleteArchivedReport(id: number): Promise<void> {
  return apiFetch<void>(`/api/v1/reports/archive/${id}`, { method: "DELETE" });
}

export async function generateDailyReport(
  body: Pick<ReportGenerateRequest, "day_key" | "include_debug">
): Promise<ReportGenerateResponse> {
  return apiFetch<ReportGenerateResponse>("/api/v1/reports/daily/generate", {
    method: "POST",
    body: JSON.stringify({
      day_key: body.day_key,
      include_debug: body.include_debug ?? false,
    }),
  });
}

export async function generateWeeklyReport(
  body: Pick<ReportGenerateRequest, "date_range_start" | "date_range_end" | "include_debug">
): Promise<ReportGenerateResponse> {
  return apiFetch<ReportGenerateResponse>("/api/v1/reports/weekly/generate", {
    method: "POST",
    body: JSON.stringify({
      date_range_start: body.date_range_start,
      date_range_end: body.date_range_end,
      include_debug: body.include_debug ?? false,
    }),
  });
}

export async function generateMonthlyReport(
  body: Pick<ReportGenerateRequest, "date_range_start" | "date_range_end" | "include_debug">
): Promise<ReportGenerateResponse> {
  return apiFetch<ReportGenerateResponse>("/api/v1/reports/monthly/generate", {
    method: "POST",
    body: JSON.stringify({
      date_range_start: body.date_range_start,
      date_range_end: body.date_range_end,
      include_debug: body.include_debug ?? false,
    }),
  });
}

/** 强制返回 trace；`report_type` 默认 weekly（后端模型默认值） */
export async function generateReportDebug(body: ReportDebugRequest): Promise<ReportGenerateResponse> {
  return apiFetch<ReportGenerateResponse>("/api/v1/reports/debug/generate", {
    method: "POST",
    body: JSON.stringify({
      report_type: body.report_type ?? "weekly",
      day_key: body.day_key ?? null,
      date_range_start: body.date_range_start ?? null,
      date_range_end: body.date_range_end ?? null,
      include_debug: true,
    }),
  });
}

/** POST /api/v1/rag/query，NDJSON 流式（stream=true）。 */
export async function ragQueryStream(
  body: { question: string; include_debug?: boolean },
  onLine: (ev: RagStreamEvent) => void
): Promise<void> {
  const h = new Headers();
  h.set("Content-Type", "application/json");
  const tok = getToken();
  if (tok) h.set("Authorization", `Bearer ${tok}`);
  const r = await fetch(`${API_BASE}/api/v1/rag/query`, {
    method: "POST",
    headers: h,
    body: JSON.stringify({ ...body, stream: true }),
  });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(text || r.statusText);
  }
  const reader = r.body?.getReader();
  if (!reader) throw new Error("无响应体");
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, i).trim();
      buf = buf.slice(i + 1);
      if (!line) continue;
      onLine(JSON.parse(line) as RagStreamEvent);
    }
  }
}
