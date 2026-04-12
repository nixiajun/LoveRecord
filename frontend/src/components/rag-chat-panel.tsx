"use client";

import { useState } from "react";
import { ragQueryStream, type RagStreamEvent } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function RagChatPanel() {
  const [q, setQ] = useState("");
  const [out, setOut] = useState("");
  const [cites, setCites] = useState<unknown[]>([]);
  const [busy, setBusy] = useState(false);
  const [routerPath, setRouterPath] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function send() {
    const text = q.trim();
    if (!text || busy) return;
    setBusy(true);
    setOut("");
    setCites([]);
    setRouterPath(null);
    setErr(null);
    try {
      await ragQueryStream({ question: text, include_debug: true }, (ev: RagStreamEvent) => {
        if (ev.event === "meta") {
          setRouterPath(ev.router_path ?? null);
        }
        if (ev.event === "token") {
          setOut((o) => o + ev.text);
        }
        if (ev.event === "done") {
          setCites(ev.citations ?? []);
        }
      });
    } catch (e) {
      setErr(e instanceof Error ? e.message : "请求失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">聊天回忆助手</CardTitle>
        <p className="text-sm text-[var(--muted)] font-normal">
          基于你们已上传的对话：结构化过滤 + 关键词 + 向量混合召回，流式回答。
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        <textarea
          className="w-full min-h-[88px] rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--ring)]"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="例如：上周我们聊了什么？她是不是说过想吃火锅？"
          disabled={busy}
        />
        <Button type="button" onClick={() => void send()} disabled={busy || !q.trim()}>
          {busy ? "生成中…" : "发送（流式）"}
        </Button>
        {err && <p className="text-sm text-red-500">{err}</p>}
        {routerPath && (
          <p className="text-xs text-[var(--muted)]">召回路径：{routerPath}</p>
        )}
        <div className="whitespace-pre-wrap rounded-lg border border-[var(--border)] bg-[var(--muted)]/5 p-3 text-sm min-h-[100px]">
          {out || (!busy ? <span className="text-[var(--muted)]">回答会显示在这里。</span> : null)}
        </div>
        {cites.length > 0 && (
          <details className="text-sm">
            <summary className="cursor-pointer text-[var(--muted)]">
              引用（{cites.length} 条）
            </summary>
            <pre className="mt-2 max-h-56 overflow-auto rounded border border-[var(--border)] p-2 text-xs">
              {JSON.stringify(cites, null, 2)}
            </pre>
          </details>
        )}
      </CardContent>
    </Card>
  );
}
