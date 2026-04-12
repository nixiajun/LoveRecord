"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";

type Log = {
  id: number;
  query_text: string;
  answer_text: string | null;
  status: string;
  created_at: string | null;
};

export default function BotLogsPage() {
  const { data } = useQuery({
    queryKey: ["bot-logs"],
    queryFn: () => apiFetch<Log[]>("/api/v1/bot/logs"),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Bot 查询日志</h1>
      <div className="space-y-4">
        {(data ?? []).map((r) => (
          <Card key={r.id}>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex justify-between gap-2">
                <span className="truncate">#{r.id}</span>
                <span className="text-xs font-normal text-[var(--muted)]">{r.status}</span>
              </CardTitle>
              <p className="text-xs text-[var(--muted)]">{r.created_at}</p>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div>
                <p className="text-xs text-[var(--muted)] mb-1">提问</p>
                <p className="whitespace-pre-wrap">{r.query_text}</p>
              </div>
              <div>
                <p className="text-xs text-[var(--muted)] mb-1">回答</p>
                <p className="whitespace-pre-wrap text-[var(--muted)]">
                  {r.answer_text ?? "—"}
                </p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
