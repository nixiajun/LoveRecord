"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useUploadProgress } from "@/contexts/upload-progress-context";
import { apiFetch } from "@/lib/api";

type Upload = {
  id: number;
  original_filename: string;
  parse_status: string;
  parse_error: string | null;
  upload_date: string;
};

function needsMappingHint(filename: string) {
  const lower = filename.toLowerCase();
  return lower.endsWith(".csv") || lower.endsWith(".json");
}

export default function UploadsPage() {
  const qc = useQueryClient();
  const { startUpload, job: uploadJob } = useUploadProgress();
  const uploadBusy =
    uploadJob.phase === "uploading" || uploadJob.phase === "processing";
  const [file, setFile] = useState<File | null>(null);
  const [timeKey, setTimeKey] = useState("");
  const [speakerKey, setSpeakerKey] = useState("");
  const [contentKey, setContentKey] = useState("");
  const [listKey, setListKey] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  const showMapping = useMemo(() => (file ? needsMappingHint(file.name) : false), [file]);

  const { data: list } = useQuery({
    queryKey: ["uploads"],
    queryFn: () => apiFetch<Upload[]>("/api/v1/uploads"),
  });

  const delUpload = useMutation({
    mutationFn: (id: number) => apiFetch<void>(`/api/v1/uploads/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["uploads"] });
      qc.invalidateQueries({ queryKey: ["days"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      setMsg("已删除该上传及对应消息");
    },
    onError: (e: Error) => setMsg(e.message),
  });

  function buildParserOptions(): string | undefined {
    const t = timeKey.trim();
    const s = speakerKey.trim();
    const c = contentKey.trim();
    const l = listKey.trim();
    if (!t && !s && !c && !l) return undefined;
    if (!t || !s || !c) {
      throw new Error("使用自定义映射时，请填写时间、发言人、内容三个字段名（与文件完全一致）");
    }
    const obj: Record<string, string> = {
      time_key: t,
      speaker_key: s,
      content_key: c,
    };
    if (l) obj.json_list_key = l;
    return JSON.stringify(obj);
  }

  async function submit() {
    if (!file) {
      setMsg("请先选择文件");
      return;
    }
    setMsg(null);
    let opts: string | undefined;
    try {
      opts = buildParserOptions();
    } catch (e) {
      setMsg((e as Error).message);
      return;
    }
    try {
      await startUpload(file, opts);
      setMsg("上传并处理完成（详见顶部提示）");
      setFile(null);
    } catch (e) {
      setMsg((e as Error).message || "上传失败");
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">上传聊天记录</h1>
      <Card>
        <CardHeader>
          <CardTitle>选择文件</CardTitle>
          <p className="text-sm text-[var(--muted)]">
            支持 .txt / .csv / .json。.csv / .json 可指定列名或键名（含嵌套，如{" "}
            <code className="text-xs">meta.time</code>）。
          </p>
          <p className="text-xs text-amber-700 dark:text-amber-300/90 rounded-lg bg-amber-500/10 border border-amber-200/60 dark:border-amber-900/40 px-3 py-2 leading-relaxed">
            大文件上传时，顶部会显示<strong>实时进度</strong>。可切换到其他页面浏览，处理会在后台继续；请勿
            <strong>关闭或刷新浏览器标签</strong>，否则可能中断请求。关闭标签页前系统会尝试提示确认。
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <input
            type="file"
            accept=".txt,.csv,.json"
            className="text-sm block"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setMsg(null);
            }}
          />
          {file && (
            <p className="text-sm text-[var(--muted)]">
              已选：<span className="text-[var(--fg)]">{file.name}</span>
            </p>
          )}

          {showMapping && (
            <div className="space-y-3 rounded-xl border border-[var(--border)] p-4">
              <p className="text-sm font-medium">自定义字段映射（可选）</p>
              <p className="text-xs text-[var(--muted)] leading-relaxed">
                与 CSV 表头或 JSON 每条消息里的键名<strong>完全一致</strong>；不填则使用默认智能识别（CSV
                需含 time/speaker/content 等价列，JSON 需数组或 {"{"}&quot;messages&quot;: []{"}"}）。
              </p>
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <Label htmlFor="tk">时间字段</Label>
                  <Input
                    id="tk"
                    placeholder="如 time、发送时间、meta.at"
                    value={timeKey}
                    onChange={(e) => setTimeKey(e.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="sk">发言人字段</Label>
                  <Input
                    id="sk"
                    placeholder="如 speaker、昵称、from.name"
                    value={speakerKey}
                    onChange={(e) => setSpeakerKey(e.target.value)}
                  />
                </div>
                <div className="sm:col-span-2">
                  <Label htmlFor="ck">内容字段</Label>
                  <Input
                    id="ck"
                    placeholder="如 content、话、body"
                    value={contentKey}
                    onChange={(e) => setContentKey(e.target.value)}
                  />
                </div>
                <div className="sm:col-span-2">
                  <Label htmlFor="lk">消息列表路径（仅 JSON 根为对象时）</Label>
                  <Input
                    id="lk"
                    placeholder="如 messages、data.records；根即为数组可留空"
                    value={listKey}
                    onChange={(e) => setListKey(e.target.value)}
                  />
                </div>
              </div>
            </div>
          )}

          <Button
            type="button"
            variant="outline"
            disabled={uploadBusy || !file}
            onClick={() => void submit()}
          >
            {uploadBusy ? "处理中…" : "上传并解析"}
          </Button>
          {uploadBusy && (
            <div className="space-y-1">
              <div className="h-2 rounded-full bg-[var(--border)] overflow-hidden">
                <div
                  className="h-full bg-[var(--accent)] transition-[width] duration-300 ease-out"
                  style={{
                    width:
                      uploadJob.phase === "processing"
                        ? "100%"
                        : `${Math.max(2, uploadJob.progress)}%`,
                  }}
                />
              </div>
              <p className="text-xs text-[var(--muted)]">
                {uploadJob.phase === "uploading" &&
                  `上传进度约 ${uploadJob.progress}%（上传完成后进入服务器解析阶段）`}
                {uploadJob.phase === "processing" && (uploadJob.message || "服务器处理中…")}
              </p>
            </div>
          )}
          {msg && <p className="text-sm whitespace-pre-wrap">{msg}</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>上传历史</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {list?.map((u) => (
            <div key={u.id} className="rounded-xl border border-[var(--border)] p-3 space-y-2">
              <div className="flex justify-between gap-2">
                <span className="font-medium truncate">{u.original_filename}</span>
                <span className="text-[var(--muted)] shrink-0">{u.parse_status}</span>
              </div>
              <p className="text-xs text-[var(--muted)]">日历日 {u.upload_date} · id #{u.id}</p>
              {u.parse_error && (
                <p className="text-xs text-red-500 whitespace-pre-wrap">{u.parse_error}</p>
              )}
              <div className="flex flex-wrap gap-2">
                <Link href={`/uploads/${u.id}`}>
                  <Button type="button" variant="outline" className="text-xs py-1.5 px-3">
                    查看详情
                  </Button>
                </Link>
                <Button
                  type="button"
                  variant="outline"
                  className="text-red-500 border-red-200 dark:border-red-900 text-xs"
                  disabled={delUpload.isPending}
                  onClick={() => {
                    if (
                      confirm(
                        `删除上传「${u.original_filename}」？将移除该次导入产生的全部消息并更新按日聚合与检索块。`
                      )
                    ) {
                      delUpload.mutate(u.id);
                    }
                  }}
                >
                  删除此上传
                </Button>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
