"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { MemorialTicker } from "@/components/memorial-ticker";
import { SmartBotPanel } from "@/components/smart-bot-panel";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";

type Dashboard = {
  recent_uploads: { id: number; filename: string; parse_status: string; upload_date: string }[];
  recent_summaries: { day_key: string; title: string; generation_status: string }[];
  today_message_count: number;
  today_summary_status: string | null;
  bot_queries_7d: number;
};

type MemorialRow = { id: number; title: string; occurred_at: string };

export default function DashboardPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => apiFetch<Dashboard>("/api/v1/dashboard"),
  });

  const { data: memorials } = useQuery({
    queryKey: ["memorials"],
    queryFn: () => apiFetch<MemorialRow[]>("/api/v1/memorials"),
  });

  if (isLoading) return <p className="text-[var(--muted)] py-12 text-center">加载中…</p>;
  if (error)
    return (
      <p className="text-red-500 py-12 text-center">
        无法加载。请确认已登录且后端运行在 {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}
      </p>
    );

  return (
    <div className="space-y-6">
      {/* 欢迎语 */}
      <div className="text-center py-2">
        <h1 className="text-xl font-semibold bg-gradient-to-r from-rose-500 to-pink-500 bg-clip-text text-transparent">
          你们的恋爱小世界
        </h1>
        <p className="text-xs text-[var(--muted)] mt-1">每一天都值得被记住</p>
      </div>

      <MemorialTicker items={memorials ?? []} />

      {/* 统计卡片 */}
      <div className="grid gap-3 grid-cols-3">
        <Card className="text-center">
          <CardContent className="py-4">
            <p className="text-2xl font-bold tabular-nums text-[var(--accent)]">{data?.today_message_count ?? 0}</p>
            <p className="text-[10px] text-[var(--muted)] mt-0.5">今日消息</p>
          </CardContent>
        </Card>
        <Card className="text-center">
          <CardContent className="py-4">
            <p className="text-sm font-medium text-[var(--fg)]">{data?.today_summary_status ?? "未生成"}</p>
            <p className="text-[10px] text-[var(--muted)] mt-0.5">今日简报</p>
          </CardContent>
        </Card>
        <Card className="text-center">
          <CardContent className="py-4">
            <p className="text-2xl font-bold tabular-nums text-[var(--accent)]">{data?.bot_queries_7d ?? 0}</p>
            <p className="text-[10px] text-[var(--muted)] mt-0.5">7天问答</p>
          </CardContent>
        </Card>
      </div>

      {/* 智能助理 */}
      <SmartBotPanel />

      {/* 最近动态 */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>📤 最近上传</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {(data?.recent_uploads?.length ?? 0) === 0 && (
              <p className="text-[var(--muted)] text-xs">暂无，去「上传」页试试吧</p>
            )}
            {data?.recent_uploads?.map((u) => (
              <div key={u.id} className="flex justify-between gap-2 py-1">
                <span className="truncate text-xs">{u.filename}</span>
                <span className="text-[var(--muted)] shrink-0 text-xs">{u.parse_status}</span>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>📋 最近简报</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            {(data?.recent_summaries?.length ?? 0) === 0 && (
              <p className="text-[var(--muted)] text-xs">尚未生成简报</p>
            )}
            {data?.recent_summaries?.map((s) => (
              <Link
                key={s.day_key}
                href={`/summaries/daily/${s.day_key}`}
                className="block rounded-xl hover:bg-[var(--warm)] px-2 py-1.5 -mx-2 transition-colors"
              >
                <span className="text-xs font-medium">{s.day_key}</span>
                <span className="text-[var(--muted)] text-xs ml-2">{s.title}</span>
              </Link>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
