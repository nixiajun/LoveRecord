"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiFetch } from "@/lib/api";

type DayRow = { day_key: string; message_count: number };
type DaysResponse = { days: DayRow[]; day_start_hour: number };

export default function DaysPage() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const { data } = useQuery({
    queryKey: ["days"],
    queryFn: () => apiFetch<DaysResponse>("/api/v1/messages/days"),
  });

  const delDay = useMutation({
    mutationFn: (dayKey: string) =>
      apiFetch<void>(`/api/v1/messages/day/${encodeURIComponent(dayKey)}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["days"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const days = data?.days ?? [];
  const dayStartHour = data?.day_start_hour ?? 0;
  const filtered = days.filter((d) => d.day_key.includes(q.trim()));

  const timeRangeLabel = dayStartHour > 0
    ? `${dayStartHour}:00 ~ 次日 ${dayStartHour}:00`
    : "0:00 ~ 24:00";

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold">💬 按日查看</h1>
        {dayStartHour > 0 && (
          <p className="text-xs text-[var(--muted)] mt-1">
            每天时间范围：{timeRangeLabel}（凌晨 {dayStartHour} 点前的消息归前一天）
          </p>
        )}
      </div>
      <Card>
        <CardContent className="py-3">
          <Input placeholder="筛选日期，如 2026-04" value={q} onChange={(e) => setQ(e.target.value)} />
        </CardContent>
      </Card>
      <div className="grid gap-2 sm:grid-cols-2">
        {filtered.map((d) => (
          <Card key={d.day_key}>
            <CardContent className="py-3 flex items-center justify-between gap-3">
              <Link
                href={`/days/${d.day_key}`}
                className="flex-1 min-w-0 hover:text-[var(--accent)] transition-colors"
              >
                <span className="font-medium text-sm block">{d.day_key}</span>
                <span className="text-[var(--muted)] text-xs">{d.message_count} 条</span>
              </Link>
              <Button
                type="button"
                variant="outline"
                className="shrink-0 text-red-500 border-red-200 dark:border-red-900 text-xs"
                disabled={delDay.isPending}
                onClick={(e) => {
                  e.preventDefault();
                  if (confirm(`删除 ${d.day_key} 全部消息？不可恢复。`)) {
                    delDay.mutate(d.day_key);
                  }
                }}
              >
                删除
              </Button>
            </CardContent>
          </Card>
        ))}
        {filtered.length === 0 && (
          <p className="text-sm text-[var(--muted)] col-span-2 text-center py-8">暂无聊天记录</p>
        )}
      </div>
    </div>
  );
}
