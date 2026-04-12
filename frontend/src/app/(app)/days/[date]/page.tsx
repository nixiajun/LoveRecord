"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

type DayResp = {
  day_key: string;
  message_count: number;
  day_start_hour: number;
  messages: {
    id: number;
    name: string;
    content: string;
    time: string;
    type: string;
    seq: number;
    url: string | null;
  }[];
};

type Me = { display_name: string; chat_aliases?: string[] };

function normName(s: string) {
  return s.trim();
}

function isSelfMessage(name: string, me: Me | undefined) {
  if (!me) return false;
  const n = normName(name);
  if (!n) return false;
  if (n === normName(me.display_name)) return true;
  const aliases = me.chat_aliases ?? [];
  return aliases.some((a) => normName(a) === n);
}

function formatMsgClock(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function ChatImage({ url }: { url: string }) {
  const [broken, setBroken] = useState(false);

  if (broken) {
    return (
      <p className="text-xs opacity-80">
        无法预览，{" "}
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="underline"
        >
          打开链接
        </a>
      </p>
    );
  }

  return (
    <img
      src={url}
      alt=""
      className="max-h-28 max-w-[min(100%,120px)] sm:max-h-32 sm:max-w-[136px] rounded-md object-contain"
      onError={() => setBroken(true)}
    />
  );
}

function captionWithMedia(content: string) {
  const t = content.trim();
  if (!t) return false;
  return !/^\[(图片|表情包|表情|动画表情)\]$/.test(t);
}

function BubbleContent({ m }: { m: DayResp["messages"][number] }) {
  const url = m.url?.trim();
  if (url) {
    return (
      <div className="space-y-2">
        {m.content && captionWithMedia(m.content) ? (
          <p className="whitespace-pre-wrap break-words leading-relaxed">{m.content}</p>
        ) : null}
        <ChatImage url={url} />
      </div>
    );
  }
  return <p className="whitespace-pre-wrap break-words leading-relaxed">{m.content}</p>;
}

export default function DayDetailPage() {
  const params = useParams<{ date: string }>();
  const router = useRouter();
  const dayKey = params.date;
  const qc = useQueryClient();

  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<Me>("/api/v1/auth/me"),
  });

  const { data } = useQuery({
    queryKey: ["day", dayKey],
    queryFn: () => apiFetch<DayResp>(`/api/v1/messages/day/${dayKey}`),
    enabled: !!dayKey,
  });

  const gen = useMutation({
    mutationFn: () =>
      apiFetch(`/api/v1/summaries/daily/${dayKey}/generate`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["summary", dayKey] }),
  });

  const delDay = useMutation({
    mutationFn: () =>
      apiFetch<void>(`/api/v1/messages/day/${encodeURIComponent(dayKey!)}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["days"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      router.push("/days");
    },
  });

  const delMsg = useMutation({
    mutationFn: (id: number) => apiFetch<void>(`/api/v1/messages/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["day", dayKey] });
      qc.invalidateQueries({ queryKey: ["days"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{dayKey}</h1>
          {(data?.day_start_hour ?? 0) > 0 && (
            <p className="text-xs text-[var(--muted)] mt-0.5">
              {data!.day_start_hour}:00 ~ 次日 {data!.day_start_hour}:00
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href={`/summaries/daily/${dayKey}`}>
            <Button variant="outline" type="button">
              查看简报
            </Button>
          </Link>
          <Button type="button" disabled={gen.isPending} onClick={() => gen.mutate()}>
            {gen.isPending ? "生成中…" : "生成简报"}
          </Button>
          <Button
            type="button"
            variant="outline"
            className="text-red-500 border-red-200 dark:border-red-900"
            disabled={delDay.isPending || (data?.message_count ?? 0) === 0}
            onClick={() => {
              if (confirm(`删除 ${dayKey} 当日全部消息？`)) delDay.mutate();
            }}
          >
            {delDay.isPending ? "删除中…" : "删除当日全部"}
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>统计</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-[var(--muted)]">
          共 {data?.message_count ?? 0} 条消息
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>消息</CardTitle>
          <p className="text-xs text-[var(--muted)] font-normal">
            绿色气泡为「我」：与显示名或设置里填写的<strong>微信昵称</strong>任一条一致即可；另一侧为对方。
          </p>
        </CardHeader>
        <CardContent className="p-0 sm:p-0">
          <div className="mx-0 rounded-b-xl px-2 py-4 sm:px-4 min-h-[320px] bg-neutral-200/55 dark:bg-zinc-900/45 space-y-1">
            <div className="space-y-3">
              {(data?.messages ?? []).map((m) => {
                const self = isSelfMessage(m.name, me);
                return (
                  <div
                    key={m.id}
                    className={cn(
                      "flex w-full group",
                      self ? "justify-end" : "justify-start"
                    )}
                  >
                    <div
                      className={cn(
                        "flex max-w-[min(100%,420px)] flex-col",
                        self ? "items-end" : "items-start"
                      )}
                    >
                      <span
                        className={cn(
                          "text-xs text-neutral-600 dark:text-neutral-400 mb-1 px-1 max-w-full truncate",
                          self ? "text-right" : "text-left"
                        )}
                      >
                        {m.name}
                      </span>
                      <div
                        className={cn(
                          "rounded-xl px-3 py-2 text-sm shadow-sm border",
                          self
                            ? "bg-[#95ec69] dark:bg-emerald-900/85 dark:text-emerald-50 text-neutral-900 border-emerald-600/20 dark:border-emerald-700/40 rounded-tr-sm"
                            : "bg-white dark:bg-zinc-800 text-[var(--fg)] border-black/[0.06] dark:border-white/10 rounded-tl-sm"
                        )}
                      >
                        <BubbleContent m={m} />
                      </div>
                      <div
                        className={cn(
                          "flex items-center gap-2 mt-1 px-1",
                          self ? "flex-row-reverse" : "flex-row"
                        )}
                      >
                        <span className="text-[11px] text-neutral-500 dark:text-neutral-500 tabular-nums">
                          {formatMsgClock(m.time)}
                        </span>
                        <button
                          type="button"
                          className="text-[11px] text-red-500/90 hover:text-red-600 hover:underline disabled:opacity-50"
                          disabled={delMsg.isPending}
                          onClick={() => {
                            if (confirm("删除本条消息？")) delMsg.mutate(m.id);
                          }}
                        >
                          删除
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
