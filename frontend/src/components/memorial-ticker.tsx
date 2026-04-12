"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export type MemorialItem = {
  id: number;
  title: string;
  occurred_at: string;
};

function pad2(n: number) {
  return String(n).padStart(2, "0");
}

function splitDuration(totalMs: number) {
  const sec = Math.floor(totalMs / 1000);
  const s = sec % 60;
  const m = Math.floor(sec / 60) % 60;
  const h = Math.floor(sec / 3600) % 24;
  const d = Math.floor(sec / 86400);
  return { d, h, m, s };
}

function MemorialRow({ item, nowMs }: { item: MemorialItem; nowMs: number }) {
  const target = new Date(item.occurred_at).getTime();
  const isFuture = target > nowMs;
  const diff = isFuture ? target - nowMs : nowMs - target;
  const { d, h, m, s } = splitDuration(diff);

  return (
    <div className="rounded-xl border border-[var(--border)] bg-black/[0.02] dark:bg-white/[0.03] p-4">
      <div className="flex items-start justify-between gap-2 mb-2">
        <h3 className="font-medium text-[var(--fg)]">{item.title}</h3>
        <span className="text-xs text-[var(--muted)] shrink-0 tabular-nums">
          {new Date(item.occurred_at).toLocaleString()}
        </span>
      </div>
      <p className="text-xs text-[var(--muted)] mb-2">{isFuture ? "距离这一刻还有" : "从这一刻起已经"}</p>
      <p className="text-2xl sm:text-3xl font-semibold tabular-nums tracking-tight text-[var(--accent)]">
        <span>{d}</span>
        <span className="text-sm font-normal text-[var(--muted)] mx-1">天</span>
        <span>{pad2(h)}</span>
        <span className="text-sm font-normal text-[var(--muted)] mx-0.5">:</span>
        <span>{pad2(m)}</span>
        <span className="text-sm font-normal text-[var(--muted)] mx-0.5">:</span>
        <span>{pad2(s)}</span>
      </p>
      <p className="text-xs text-[var(--muted)] mt-1">时 · 分 · 秒（每秒刷新）</p>
    </div>
  );
}

export function MemorialTicker({ items }: { items: MemorialItem[] }) {
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  if (items.length === 0) {
    return (
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-2">
          <CardTitle>纪念日</CardTitle>
          <Link href="/memorials" className="text-sm text-[var(--accent)] hover:underline">
            去添加
          </Link>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-[var(--muted)]">还没有纪念日，添加第一个重要时刻吧。</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle>纪念日</CardTitle>
        <Link href="/memorials" className="text-sm text-[var(--accent)] hover:underline">
          管理
        </Link>
      </CardHeader>
      <CardContent className="space-y-4">
        {items.map((item) => (
          <MemorialRow key={item.id} item={item} nowMs={nowMs} />
        ))}
      </CardContent>
    </Card>
  );
}
