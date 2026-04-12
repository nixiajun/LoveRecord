"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import {
  archiveReport,
  deleteArchivedReport,
  enqueueReportJob,
  getArchivedReport,
  listArchivedReports,
  listReportJobs,
  type ReportCitation,
  type ReportGenerateResponse,
  type ReportJobOut,
  type ReportType,
  streamReportGenerate,
  type SavedReportDetailOut,
  type SavedReportListItem,
} from "@/lib/api";
import { defaultMonthRangeRef, defaultWeekRangeRef, toYMDLocal } from "@/lib/date-helpers";

type GenTabKey = "daily" | "weekly" | "monthly" | "custom";
type MainTab = "generate" | "saved";

const genTabs: { key: GenTabKey; label: string }[] = [
  { key: "daily", label: "日报" },
  { key: "weekly", label: "周报" },
  { key: "monthly", label: "月报" },
  { key: "custom", label: "自定义" },
];

function pickStructured(
  sec: Record<string, unknown> | undefined,
  keys: string[]
): Array<{ key: string; value: unknown }> {
  if (!sec) return [];
  return keys
    .filter((k) => k in sec && sec[k] != null && sec[k] !== "")
    .map((k) => ({ key: k, value: sec[k] }));
}

function formatValue(v: unknown): string {
  if (v == null) return "";
  if (Array.isArray(v)) return v.map((x) => String(x)).join("、");
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function downloadReportHtml(r: ReportGenerateResponse) {
  const t = escapeHtml(r.final.title || "报表");
  const body = escapeHtml(r.final.body_web || "");
  const html = `<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"/><title>${t}</title></head><body>
<h1>${t}</h1><p>${r.report_type} · ${r.date_range_start} ～ ${r.date_range_end}</p>
<article style="white-space:pre-wrap;font-family:system-ui,sans-serif;line-height:1.6">${body}</article>
</body></html>`;
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `恋爱记录报表-${r.date_range_start}-${r.report_type}.html`;
  a.click();
  URL.revokeObjectURL(a.href);
}

function jobStatusLabel(status: string): string {
  const m: Record<string, string> = {
    pending: "排队中",
    running: "生成中",
    completed: "已完成",
    failed: "失败",
  };
  return m[status] ?? status;
}

function jobRangeLabel(j: ReportJobOut): string {
  if (j.report_type === "daily" && j.day_key) return j.day_key;
  return `${j.date_range_start}～${j.date_range_end}`;
}

function savedDetailToResponse(d: SavedReportDetailOut): ReportGenerateResponse {
  const cites = Array.isArray(d.citations) ? (d.citations as ReportCitation[]) : [];
  return {
    report_type: d.report_type as ReportType,
    date_range_start: d.date_range_start,
    date_range_end: d.date_range_end,
    final: {
      title: d.title,
      body_web: d.body_web,
      body_wechat: d.body_wechat,
      structured_sections: (d.structured_sections as Record<string, unknown>) || {},
    },
    citations: cites,
    trace: d.trace as ReportGenerateResponse["trace"],
  };
}

function ReportResultView({
  result,
  showTrace,
  expanded,
  onToggleExpand,
}: {
  result: ReportGenerateResponse;
  showTrace: boolean;
  expanded: boolean;
  onToggleExpand: () => void;
}) {
  const structuredPairs = useMemo(() => {
    if (!result?.final?.structured_sections) return [];
    return pickStructured(result.final.structured_sections as Record<string, unknown>, [
      "overview",
      "main_topics",
      "warm_moments",
      "friction_points",
      "mood_tags",
      "one_liner",
    ]);
  }, [result]);

  const printReport = () => window.print();

  return (
    <Card className="border-[var(--border)]">
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">{result.final.title || "报表"}</CardTitle>
            <p className="text-xs text-[var(--muted)] mt-1">
              {result.report_type} · {result.date_range_start} ～ {result.date_range_end}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" className="text-xs" onClick={onToggleExpand}>
              {expanded ? "全部收起" : "全部展开"}
            </Button>
            <Button type="button" variant="outline" className="text-xs" onClick={printReport}>
              导出 PDF（打印）
            </Button>
            <Button
              type="button"
              variant="outline"
              className="text-xs"
              onClick={() => downloadReportHtml(result)}
            >
              下载 HTML
            </Button>
          </div>
        </div>
      </CardHeader>
      <div className="report-print-area">
        <CardContent className="space-y-4 pt-0">
          <div className="hidden print:block pb-4 border-b border-[var(--border)]">
            <h2 className="text-lg font-semibold">{result.final.title || "报表"}</h2>
            <p className="text-sm text-[var(--muted)]">
              {result.report_type} · {result.date_range_start} ～ {result.date_range_end}
            </p>
          </div>
        {structuredPairs.length > 0 && (
          <details open={expanded} className="rounded-xl border border-[var(--border)] p-4 text-sm group">
            <summary className="cursor-pointer font-medium text-[var(--fg)] list-none flex justify-between items-center print:hidden">
              <span>结构化要点</span>
              <span className="text-xs text-[var(--muted)] group-open:hidden">点击展开</span>
            </summary>
            <dl className="space-y-2 mt-3">
              {structuredPairs.map(({ key, value }) => (
                <div key={key}>
                  <dt className="text-xs uppercase tracking-wide text-[var(--muted)]">{key}</dt>
                  <dd className="text-[var(--fg)]">{formatValue(value)}</dd>
                </div>
              ))}
            </dl>
          </details>
        )}

        <details open={expanded} className="rounded-xl border border-[var(--border)] group">
          <summary className="cursor-pointer font-medium text-[var(--fg)] p-4 list-none flex justify-between items-center border-b border-[var(--border)] print:hidden">
            <span>正文（网页）</span>
            <span className="text-xs text-[var(--muted)] group-open:hidden">点击展开</span>
          </summary>
          <div className="p-4 text-sm leading-relaxed whitespace-pre-wrap">{result.final.body_web}</div>
        </details>

        {result.final.body_wechat ? (
          <details open={expanded} className="rounded-xl border border-[var(--border)] text-sm group">
            <summary className="cursor-pointer font-medium text-[var(--fg)] p-4 list-none flex justify-between items-center print:hidden">
              <span>微信短版</span>
              <span className="text-xs text-[var(--muted)] group-open:hidden">点击展开</span>
            </summary>
            <p className="px-4 pb-4 whitespace-pre-wrap text-[var(--muted)]">{result.final.body_wechat}</p>
          </details>
        ) : null}

        {result.citations?.length ? (
          <details open={expanded} className="rounded-xl border border-[var(--border)] group">
            <summary className="cursor-pointer font-medium text-[var(--fg)] p-4 text-sm list-none flex justify-between items-center print:hidden">
              <span>引用来源（{result.citations.length}）</span>
              <span className="text-xs text-[var(--muted)] group-open:hidden">点击展开</span>
            </summary>
            <ul className="px-4 pb-4 space-y-2 text-xs text-[var(--muted)]">
              {result.citations.map((c, i) => (
                <li
                  key={`${c.source_type}-${c.source_ref_id}-${i}`}
                  className="border border-[var(--border)] rounded-lg p-2"
                >
                  <span className="text-[var(--fg)]">
                    {c.source_type} #{c.source_ref_id}
                  </span>{" "}
                  · {c.day_key}
                  {c.tool_name ? ` · ${c.tool_name}` : ""}
                  <div className="mt-1 text-[var(--fg)]/90">{c.excerpt}</div>
                </li>
              ))}
            </ul>
          </details>
        ) : null}

        {result.trace && showTrace && (
          <details open={expanded} className="rounded-xl border border-dashed border-[var(--border)] text-xs group">
            <summary className="cursor-pointer font-medium text-[var(--fg)] p-4 list-none print:hidden">
              调试 trace
            </summary>
            <pre className="px-4 pb-4 overflow-auto max-h-96 text-[var(--muted)]">
              {JSON.stringify(result.trace, null, 2)}
            </pre>
          </details>
        )}
        </CardContent>
      </div>
    </Card>
  );
}

export default function ReportsCenterPage() {
  const today = useMemo(() => toYMDLocal(new Date()), []);
  const weekDef = useMemo(() => defaultWeekRangeRef(), []);
  const monthDef = useMemo(() => defaultMonthRangeRef(), []);
  const qc = useQueryClient();

  const [mainTab, setMainTab] = useState<MainTab>("generate");
  const [genTab, setGenTab] = useState<GenTabKey>("daily");
  const [dailyDay, setDailyDay] = useState(today);
  const [weekStart, setWeekStart] = useState(weekDef.start);
  const [weekEnd, setWeekEnd] = useState(weekDef.end);
  const [monthStart, setMonthStart] = useState(monthDef.start);
  const [monthEnd, setMonthEnd] = useState(monthDef.end);
  const [customStart, setCustomStart] = useState(weekDef.start);
  const [customEnd, setCustomEnd] = useState(weekDef.end);
  const [customPipeline, setCustomPipeline] = useState<"weekly" | "monthly">("weekly");
  const [includeDebug, setIncludeDebug] = useState(false);
  const [reportExpanded, setReportExpanded] = useState(true);

  const [result, setResult] = useState<ReportGenerateResponse | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [jobSubmitting, setJobSubmitting] = useState(false);
  const [autoSaved, setAutoSaved] = useState(false);
  const [lastSubmittedJobId, setLastSubmittedJobId] = useState<number | null>(null);
  const lastHandledJobRef = useRef<number | null>(null);
  const [doneSteps, setDoneSteps] = useState<string[]>([]);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [selectedSavedId, setSelectedSavedId] = useState<number | null>(null);

  const jobsQuery = useQuery({
    queryKey: ["reports-jobs"],
    queryFn: () => listReportJobs(40),
    staleTime: 0,
    refetchInterval: (query) => {
      const list = query.state.data as ReportJobOut[] | undefined;
      if (!list?.length) return false;
      const active = list.some((j) => j.status === "pending" || j.status === "running");
      return active ? 10_000 : false;
    },
  });

  const activeJobs = useMemo(
    () => (jobsQuery.data ?? []).filter((j) => j.status === "pending" || j.status === "running"),
    [jobsQuery.data]
  );

  const savedListQuery = useQuery({
    queryKey: ["reports-archive"],
    queryFn: () => listArchivedReports(50),
    enabled: mainTab === "saved",
  });

  const savedDetailQuery = useQuery({
    queryKey: ["reports-archive", selectedSavedId],
    queryFn: () => getArchivedReport(selectedSavedId!),
    enabled: mainTab === "saved" && selectedSavedId != null,
  });

  const reportTypeForRequest = useCallback((): ReportType => {
    if (genTab === "daily") return "daily";
    if (genTab === "weekly") return "weekly";
    if (genTab === "monthly") return "monthly";
    return customPipeline;
  }, [genTab, customPipeline]);

  const buildStreamBody = useCallback(() => {
    const rt = reportTypeForRequest();
    if (rt === "daily") {
      if (!dailyDay) throw new Error("请选择日期");
      return {
        report_type: "daily" as const,
        day_key: dailyDay,
        date_range_start: null,
        date_range_end: null,
        include_debug: includeDebug,
      };
    }
    let a = weekStart;
    let b = weekEnd;
    if (genTab === "monthly") {
      a = monthStart;
      b = monthEnd;
    }
    if (genTab === "custom") {
      a = customStart;
      b = customEnd;
    }
    if (!a || !b) throw new Error("请填写日期区间");
    if (a > b) throw new Error("开始日不能晚于结束日");
    return {
      report_type: rt,
      day_key: null,
      date_range_start: a,
      date_range_end: b,
      include_debug: includeDebug,
    };
  }, [
    reportTypeForRequest,
    genTab,
    dailyDay,
    weekStart,
    weekEnd,
    monthStart,
    monthEnd,
    customStart,
    customEnd,
    includeDebug,
  ]);

  useEffect(() => {
    const list = jobsQuery.data;
    if (!list?.length || lastSubmittedJobId == null) return;
    const j = list.find((x) => x.id === lastSubmittedJobId);
    if (!j) return;
    if (j.status === "completed" && j.saved_report_id != null) {
      if (lastHandledJobRef.current === j.id) return;
      lastHandledJobRef.current = j.id;
      setLastSubmittedJobId(null);
      getArchivedReport(j.saved_report_id)
        .then((d) => {
          setResult(savedDetailToResponse(d));
          setAutoSaved(true);
          setSaveMsg("生成已完成并已保存，可在「已保存」或下方预览。");
          qc.invalidateQueries({ queryKey: ["reports-archive"] });
        })
        .catch(() => {});
      return;
    }
    if (j.status === "failed") {
      if (lastHandledJobRef.current === j.id) return;
      lastHandledJobRef.current = j.id;
      setLastSubmittedJobId(null);
      setLastError(j.error_message || "生成失败");
    }
  }, [jobsQuery.data, lastSubmittedJobId, qc]);

  const openSavedReport = useCallback((savedReportId: number) => {
    setSelectedSavedId(savedReportId);
    setMainTab("saved");
    qc.invalidateQueries({ queryKey: ["reports-archive"] });
    qc.invalidateQueries({ queryKey: ["reports-archive", savedReportId] });
  }, [qc]);

  const runBackgroundJob = async () => {
    setLastError(null);
    setSaveMsg(null);
    setResult(null);
    setAutoSaved(false);
    setDoneSteps([]);
    setCurrentStep(null);
    lastHandledJobRef.current = null;
    setJobSubmitting(true);
    try {
      const job = await enqueueReportJob(buildStreamBody());
      setLastSubmittedJobId(job.id);
      setSaveMsg(
        `任务 #${job.id} 已提交后端。切换「已保存」可始终看到任务列表与状态；有进行中任务时每 30 秒自动同步列表。`
      );
      qc.invalidateQueries({ queryKey: ["reports-jobs"] });
    } catch (e) {
      setLastError((e as Error).message || "提交失败");
    } finally {
      setJobSubmitting(false);
    }
  };

  const runStream = async () => {
    setLastError(null);
    setSaveMsg(null);
    setResult(null);
    setAutoSaved(false);
    setDoneSteps([]);
    setCurrentStep(null);
    setStreaming(true);
    try {
      const body = buildStreamBody();
      await streamReportGenerate(body, (ev) => {
        if (ev.event === "agent_phase") {
          const lbl = ev.agent_label_zh + (ev.detail ? ` · ${ev.detail}` : "");
          if (ev.status === "start") setCurrentStep(`进行中：${lbl}`);
          if (ev.status === "done") {
            setDoneSteps((d) => [...d, `${lbl} ✓`]);
            setCurrentStep(null);
          }
        }
        if (ev.event === "complete") setResult(ev.body);
        if (ev.event === "error") {
          setLastError(ev.message);
          setStreaming(false);
        }
      });
    } catch (e) {
      setLastError((e as Error).message || "生成失败");
    } finally {
      setStreaming(false);
    }
  };

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!result) throw new Error("无报表可保存");
      return archiveReport({
        report_type: result.report_type,
        date_range_start: result.date_range_start,
        date_range_end: result.date_range_end,
        final: result.final,
        citations: result.citations,
        trace: result.trace ?? null,
      });
    },
    onSuccess: () => {
      setSaveMsg("已保存到「已保存」列表");
      qc.invalidateQueries({ queryKey: ["reports-archive"] });
    },
    onError: (e: Error) => setSaveMsg(e.message || "保存失败"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteArchivedReport(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["reports-archive"] });
      setSelectedSavedId(null);
    },
  });

  const displayResult =
    mainTab === "saved"
      ? savedDetailQuery.data
        ? savedDetailToResponse(savedDetailQuery.data)
        : null
      : result;

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex flex-wrap gap-2 items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">报表中心</h1>
          <p className="text-sm text-[var(--muted)] mt-1">
            默认<strong>后台生成</strong>并自动保存（避免长时间占线导致断连）。任务状态在「已保存」页顶部持续刷新，切换界面也不会丢。
            也可选流式模式看各 Agent 进度。结果可打印 PDF、下载 HTML。
          </p>
        </div>
      </div>

      <div className="flex gap-2 border-b border-[var(--border)] pb-2">
        <button
          type="button"
          onClick={() => setMainTab("generate")}
          className={cn(
            "rounded-lg px-4 py-2 text-sm font-medium",
            mainTab === "generate"
              ? "bg-[var(--accent)]/15 text-[var(--accent)]"
              : "text-[var(--muted)] hover:text-[var(--fg)]"
          )}
        >
          生成报表
        </button>
        <button
          type="button"
          onClick={() => setMainTab("saved")}
          className={cn(
            "rounded-lg px-4 py-2 text-sm font-medium",
            mainTab === "saved"
              ? "bg-[var(--accent)]/15 text-[var(--accent)]"
              : "text-[var(--muted)] hover:text-[var(--fg)]"
          )}
        >
          已保存
        </button>
      </div>

      {mainTab === "generate" && (
        <>
          <div className="flex flex-wrap gap-2">
            {genTabs.map((t) => (
              <button
                key={t.key}
                type="button"
                onClick={() => setGenTab(t.key)}
                className={cn(
                  "rounded-xl px-4 py-2 text-sm font-medium transition border",
                  genTab === t.key
                    ? "border-[var(--accent)] bg-[var(--accent)]/10 text-[var(--accent)]"
                    : "border-[var(--border)] text-[var(--muted)] hover:text-[var(--fg)]"
                )}
              >
                {t.label}
              </button>
            ))}
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                {genTab === "daily" && "生成日报"}
                {genTab === "weekly" && "生成周报"}
                {genTab === "monthly" && "生成月报"}
                {genTab === "custom" && "自定义区间报表"}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {genTab === "daily" && (
                <div className="space-y-2">
                  <Label htmlFor="daily-day">日期</Label>
                  <Input
                    id="daily-day"
                    type="date"
                    value={dailyDay}
                    onChange={(e) => setDailyDay(e.target.value)}
                  />
                </div>
              )}

              {genTab === "weekly" && (
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="ws">开始日</Label>
                    <Input
                      id="ws"
                      type="date"
                      value={weekStart}
                      onChange={(e) => setWeekStart(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="we">结束日</Label>
                    <Input
                      id="we"
                      type="date"
                      value={weekEnd}
                      onChange={(e) => setWeekEnd(e.target.value)}
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <Button
                      type="button"
                      variant="outline"
                      className="text-xs"
                      onClick={() => {
                        const d = defaultWeekRangeRef();
                        setWeekStart(d.start);
                        setWeekEnd(d.end);
                      }}
                    >
                      填入最近 7 天
                    </Button>
                  </div>
                </div>
              )}

              {genTab === "monthly" && (
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="ms">月份开始</Label>
                    <Input
                      id="ms"
                      type="date"
                      value={monthStart}
                      onChange={(e) => setMonthStart(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="me">月份结束</Label>
                    <Input
                      id="me"
                      type="date"
                      value={monthEnd}
                      onChange={(e) => setMonthEnd(e.target.value)}
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <Button
                      type="button"
                      variant="outline"
                      className="text-xs"
                      onClick={() => {
                        const d = defaultMonthRangeRef();
                        setMonthStart(d.start);
                        setMonthEnd(d.end);
                      }}
                    >
                      填入当前自然月
                    </Button>
                  </div>
                </div>
              )}

              {genTab === "custom" && (
                <div className="space-y-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="cs">开始日</Label>
                      <Input
                        id="cs"
                        type="date"
                        value={customStart}
                        onChange={(e) => setCustomStart(e.target.value)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="ce">结束日</Label>
                      <Input
                        id="ce"
                        type="date"
                        value={customEnd}
                        onChange={(e) => setCustomEnd(e.target.value)}
                      />
                    </div>
                  </div>
                  <fieldset className="space-y-2">
                    <legend className="text-sm font-medium text-[var(--fg)]">分析深度</legend>
                    <div className="flex flex-wrap gap-4">
                      <label className="flex items-center gap-2 text-sm cursor-pointer">
                        <input
                          type="radio"
                          name="pipe"
                          checked={customPipeline === "weekly"}
                          onChange={() => setCustomPipeline("weekly")}
                          className="accent-[var(--accent)]"
                        />
                        周报流程
                      </label>
                      <label className="flex items-center gap-2 text-sm cursor-pointer">
                        <input
                          type="radio"
                          name="pipe"
                          checked={customPipeline === "monthly"}
                          onChange={() => setCustomPipeline("monthly")}
                          className="accent-[var(--accent)]"
                        />
                        月报流程
                      </label>
                    </div>
                  </fieldset>
                </div>
              )}

              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={includeDebug}
                  onChange={(e) => setIncludeDebug(e.target.checked)}
                  className="rounded border-[var(--border)] accent-[var(--accent)]"
                />
                包含调试 trace
              </label>

              <div className="flex flex-wrap gap-2">
                <Button type="button" disabled={jobSubmitting || streaming} onClick={() => runBackgroundJob()}>
                  {jobSubmitting ? "提交中…" : "后台生成并自动保存"}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  disabled={jobSubmitting || streaming}
                  className="text-xs"
                  onClick={() => runStream()}
                >
                  {streaming ? "流式生成中…" : "流式生成（调试用，长任务易断线）"}
                </Button>
                {activeJobs.length > 0 && (
                  <Button type="button" variant="outline" className="text-xs" onClick={() => setMainTab("saved")}>
                    查看后台任务（{activeJobs.length} 个进行中）
                  </Button>
                )}
              </div>

              {activeJobs.length > 0 && (
                <div className="rounded-xl border border-[var(--border)] border-dashed p-3 text-xs space-y-2 text-[var(--muted)]">
                  <p className="font-medium text-[var(--fg)]">当前进行中的后台任务</p>
                  <ul className="space-y-2">
                    {activeJobs.slice(0, 5).map((j) => (
                      <li key={j.id} className="space-y-1">
                        <div className="flex items-center justify-between">
                          <span>#{j.id} · {j.report_type} · {jobRangeLabel(j)} · {jobStatusLabel(j.status)}</span>
                          {j.progress_pct != null && (
                            <span className="text-[var(--accent)] font-medium">{j.progress_pct}%</span>
                          )}
                        </div>
                        {j.current_agent && (
                          <p className="text-[var(--accent)] text-xs animate-pulse">{j.current_agent}</p>
                        )}
                        {j.progress_pct != null && (
                          <div className="w-full bg-[var(--border)] rounded-full h-1.5">
                            <div
                              className="bg-[var(--accent)] h-1.5 rounded-full transition-all duration-500"
                              style={{ width: `${j.progress_pct}%` }}
                            />
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                  <p>有进行中任务时每 30 秒拉取一次列表。</p>
                </div>
              )}

              {(streaming || doneSteps.length > 0 || currentStep) && (
                <div className="rounded-xl border border-[var(--border)] p-4 text-sm space-y-2 bg-black/[0.02] dark:bg-white/[0.03]">
                  <p className="font-medium text-[var(--fg)]">处理进度（流式模式：Agent 中文名）</p>
                  {doneSteps.length > 0 && (
                    <ol className="list-decimal list-inside space-y-1 text-[var(--muted)] text-xs max-h-40 overflow-y-auto">
                      {doneSteps.map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ol>
                  )}
                  {currentStep && (
                    <p className="text-[var(--accent)] font-medium text-sm animate-pulse">{currentStep}</p>
                  )}
                  {!streaming && doneSteps.length === 0 && !currentStep && (
                    <p className="text-xs text-[var(--muted)]">点击上方按钮开始</p>
                  )}
                </div>
              )}

              {lastError && (
                <p className="text-sm text-red-600 dark:text-red-400 whitespace-pre-wrap break-words">
                  {lastError}
                </p>
              )}

              {saveMsg && (
                <p className="text-sm text-[var(--muted)]">{saveMsg}</p>
              )}

              {result && !lastError && !autoSaved && (
                <Button
                  type="button"
                  variant="outline"
                  className="text-xs"
                  disabled={saveMutation.isPending}
                  onClick={() => saveMutation.mutate()}
                >
                  {saveMutation.isPending ? "保存中…" : "保存到已保存列表（流式结果未自动归档时）"}
                </Button>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {mainTab === "saved" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">后台生成任务</CardTitle>
            <p className="text-xs text-[var(--muted)]">
              存在排队中/生成中的任务时，每 30 秒自动同步一次列表；标题下「列表已同步于」会每次刷新后更新。各任务「服务端状态最后变更」仅在状态变化时才会变，长时间生成中不变是正常现象。
              完成后可打开归档报表。关闭页面后任务仍会在服务端执行。
            </p>
            {jobsQuery.dataUpdatedAt > 0 && !jobsQuery.isLoading && (
              <p className="text-xs font-medium text-[var(--fg)] pt-1">
                列表已同步于 {new Date(jobsQuery.dataUpdatedAt).toLocaleString()}
              </p>
            )}
          </CardHeader>
          <CardContent className="space-y-2 pb-6">
            {jobsQuery.isLoading && <p className="text-sm text-[var(--muted)]">加载任务列表…</p>}
            {jobsQuery.error && (
              <p className="text-sm text-red-500">{(jobsQuery.error as Error).message}</p>
            )}
            {!jobsQuery.isLoading && (jobsQuery.data?.length ?? 0) === 0 && (
              <p className="text-sm text-[var(--muted)]">暂无任务记录。在「生成报表」提交后台生成后会出现。</p>
            )}
            <ul className="space-y-2 max-h-64 overflow-y-auto">
              {(jobsQuery.data ?? []).map((j: ReportJobOut) => (
                <li
                  key={j.id}
                  className={cn(
                    "rounded-lg border p-3 text-sm space-y-1",
                    j.status === "failed"
                      ? "border-red-500/30 bg-red-500/5"
                      : j.status === "completed"
                        ? "border-[var(--border)]"
                        : "border-[var(--accent)]/40 bg-[var(--accent)]/5"
                  )}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium text-[var(--fg)]">
                      任务 #{j.id} · {j.report_type} · {jobRangeLabel(j)}
                    </span>
                    <span
                      className={cn(
                        "text-xs font-medium px-2 py-0.5 rounded-full",
                        j.status === "completed" && "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
                        j.status === "failed" && "bg-red-500/15 text-red-700 dark:text-red-400",
                        (j.status === "pending" || j.status === "running") &&
                          "bg-amber-500/15 text-amber-800 dark:text-amber-300"
                      )}
                    >
                      {jobStatusLabel(j.status)}
                    </span>
                  </div>
                  <p className="text-xs text-[var(--muted)]">
                    创建于 {new Date(j.created_at).toLocaleString()} · 服务端状态最后变更{" "}
                    {new Date(j.updated_at).toLocaleString()}
                    {j.include_debug ? " · 含 trace" : ""}
                  </p>
                  {j.status === "failed" && j.error_message && (
                    <p className="text-xs text-red-600 dark:text-red-400 whitespace-pre-wrap break-words">
                      {j.error_message}
                    </p>
                  )}
                  {j.status === "running" && (
                    <div className="space-y-1">
                      {j.current_agent && (
                        <p className="text-xs text-[var(--accent)] animate-pulse">{j.current_agent}</p>
                      )}
                      {j.progress_pct != null && (
                        <div className="w-full bg-[var(--border)] rounded-full h-1.5">
                          <div
                            className="bg-[var(--accent)] h-1.5 rounded-full transition-all duration-500"
                            style={{ width: `${j.progress_pct}%` }}
                          />
                        </div>
                      )}
                    </div>
                  )}
                  {j.status === "completed" && j.saved_report_id != null && (
                    <Button
                      type="button"
                      variant="outline"
                      className="text-xs mt-1"
                      onClick={() => openSavedReport(j.saved_report_id!)}
                    >
                      查看已保存报表 #{j.saved_report_id}
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {mainTab === "saved" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">已保存的报表</CardTitle>
            <p className="text-xs text-[var(--muted)]">点击一条查看；可删除不需要的归档。</p>
          </CardHeader>
          <CardContent className="space-y-2">
            {savedListQuery.isLoading && <p className="text-sm text-[var(--muted)]">加载中…</p>}
            {savedListQuery.error && (
              <p className="text-sm text-red-500">{(savedListQuery.error as Error).message}</p>
            )}
            <ul className="space-y-2 max-h-56 overflow-y-auto">
              {(savedListQuery.data ?? []).map((row: SavedReportListItem) => (
                <li
                  key={row.id}
                  className={cn(
                    "flex flex-wrap items-center justify-between gap-2 rounded-lg border p-2 text-sm",
                    selectedSavedId === row.id ? "border-[var(--accent)]" : "border-[var(--border)]"
                  )}
                >
                  <button
                    type="button"
                    className="text-left flex-1 min-w-0"
                    onClick={() => setSelectedSavedId(row.id)}
                  >
                    <span className="font-medium text-[var(--fg)] truncate block">{row.title}</span>
                    <span className="text-xs text-[var(--muted)]">
                      {row.report_type} · {row.date_range_start}～{row.date_range_end} ·{" "}
                      {new Date(row.created_at).toLocaleString()}
                    </span>
                  </button>
                  <Button
                    type="button"
                    variant="ghost"
                    className="text-xs text-red-600 shrink-0"
                    onClick={() => {
                      if (confirm("确定删除这条报表？")) deleteMutation.mutate(row.id);
                    }}
                  >
                    删除
                  </Button>
                </li>
              ))}
            </ul>
            {(savedListQuery.data?.length ?? 0) === 0 && !savedListQuery.isLoading && (
              <p className="text-sm text-[var(--muted)]">
                暂无保存记录。请在「生成报表」中用「后台生成并自动保存」，或使用流式生成后手动保存。
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {displayResult && (
        <ReportResultView
          result={displayResult}
          showTrace={!!displayResult.trace && includeDebug}
          expanded={reportExpanded}
          onToggleExpand={() => setReportExpanded((e) => !e)}
        />
      )}
    </div>
  );
}
