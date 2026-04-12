"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";

type Summary = {
  title: string;
  summary_text: string;
  highlights_json: Record<string, unknown> | null;
  mood_tags_json: unknown;
  conflict_flags_json: unknown;
};

export default function DailySummaryPage() {
  const params = useParams<{ date: string }>();
  const dayKey = params.date;

  const { data } = useQuery({
    queryKey: ["summary", dayKey],
    queryFn: () => apiFetch<Summary | null>(`/api/v1/summaries/daily/${dayKey}`),
    enabled: !!dayKey,
  });

  if (data === null)
    return (
      <p className="text-[var(--muted)]">
        暂无 {dayKey} 的简报，可在「按日」页点击生成。
      </p>
    );

  const h = ( data?.highlights_json ?? {}) as Record<string, unknown>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">{data?.title}</h1>
      <p className="text-sm text-[var(--muted)]">{dayKey}</p>

      <Card>
        <CardHeader>
          <CardTitle>概述</CardTitle>
        </CardHeader>
        <CardContent className="text-sm whitespace-pre-wrap leading-relaxed">
          {data?.summary_text}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>结构化摘要</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          {h.overview != null && (
            <section>
              <h3 className="font-medium mb-1">今日概述</h3>
              <p className="text-[var(--muted)]">{String(h.overview)}</p>
            </section>
          )}
          {Array.isArray(h.topics) && h.topics.length > 0 && (
            <section>
              <h3 className="font-medium mb-1">主要话题</h3>
              <ul className="list-disc pl-5 text-[var(--muted)]">
                {h.topics.map((t, i) => (
                  <li key={i}>{String(t)}</li>
                ))}
              </ul>
            </section>
          )}
          {Array.isArray(h.warm_moments) && h.warm_moments.length > 0 && (
            <section>
              <h3 className="font-medium mb-1">温暖时刻</h3>
              <ul className="list-disc pl-5 text-[var(--muted)]">
                {h.warm_moments.map((t, i) => (
                  <li key={i}>{String(t)}</li>
                ))}
              </ul>
            </section>
          )}
          {h.one_liner != null && (
            <section>
              <h3 className="font-medium mb-1">今日一句话</h3>
              <p className="text-[var(--accent)] font-medium">{String(h.one_liner)}</p>
            </section>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>情绪与标记</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-[var(--muted)]">
          <p>情绪标签：{JSON.stringify(data?.mood_tags_json)}</p>
          <p className="mt-2">
            潜在摩擦点：{JSON.stringify(data?.conflict_flags_json)}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
