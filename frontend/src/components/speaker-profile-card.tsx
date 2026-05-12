"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";

type SpeakerProfileData = {
  id: number;
  speaker_role: string;
  display_name: string;
  speaking_style: string;
  common_phrases: Record<string, string> | null;
  emoji_habits: Record<string, string> | null;
  emotional_patterns: Record<string, string> | null;
  topic_preferences: Record<string, string> | null;
  communication_traits: Record<string, string> | null;
  voice_sample: string;
  message_count: number;
  status: string;
  updated_at: string | null;
};

type ProfilesResponse = { profiles: SpeakerProfileData[] };

function ProfileContent({ p }: { p: SpeakerProfileData }) {
  const roleLabel = p.speaker_role === "owner" ? "自己" : "对象";
  return (
    <div className="space-y-3 text-sm">
      {/* 说话风格 */}
      <div>
        <p className="text-xs font-medium text-rose-500 mb-1">说话风格</p>
        <p className="text-[var(--muted)] leading-relaxed">{p.speaking_style}</p>
      </div>

      {/* voice_sample */}
      {p.voice_sample && (
        <div>
          <p className="text-xs font-medium text-rose-500 mb-1">代表性语句</p>
          <div className="bg-[var(--warm)] rounded-xl px-3 py-2 text-xs italic text-[var(--fg)]">
            「{p.voice_sample}」
          </div>
        </div>
      )}

      {/* 沟通特征 */}
      {p.communication_traits && Object.keys(p.communication_traits).length > 0 && (
        <div>
          <p className="text-xs font-medium text-rose-500 mb-1">沟通特征</p>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(p.communication_traits).map(([k, v]) => (
              <span key={k} className="text-xs bg-rose-50 dark:bg-rose-900/20 text-rose-600 dark:text-rose-300 rounded-full px-2 py-0.5">
                {k}: {v}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* emoji */}
      {p.emoji_habits && Object.keys(p.emoji_habits).length > 0 && (
        <div>
          <p className="text-xs font-medium text-rose-500 mb-1">表情习惯</p>
          <div className="space-y-0.5">
            {Object.entries(p.emoji_habits).slice(0, 4).map(([k, v]) => (
              <p key={k} className="text-xs text-[var(--muted)]">{k}: {v}</p>
            ))}
          </div>
        </div>
      )}

      {/* 情绪模式 */}
      {p.emotional_patterns && Object.keys(p.emotional_patterns).length > 0 && (
        <div>
          <p className="text-xs font-medium text-rose-500 mb-1">情绪表达</p>
          <div className="space-y-0.5">
            {Object.entries(p.emotional_patterns).map(([k, v]) => (
              <p key={k} className="text-xs text-[var(--muted)]">{k}: {v}</p>
            ))}
          </div>
        </div>
      )}

      {/* 常用词 */}
      {p.common_phrases && Object.keys(p.common_phrases).length > 0 && (
        <div>
          <p className="text-xs font-medium text-rose-500 mb-1">口头禅</p>
          <div className="flex flex-wrap gap-1">
            {Object.entries(p.common_phrases).slice(0, 8).map(([k, v]) => (
              <span key={k} className="text-xs bg-pink-50 dark:bg-pink-900/20 text-pink-600 dark:text-pink-300 rounded-full px-2 py-0.5">
                &quot;{k}&quot;
              </span>
            ))}
          </div>
        </div>
      )}

      <p className="text-[10px] text-[var(--muted)]">
        基于 {p.message_count} 条消息蒸馏 · {p.status === "ready" ? "已生成" : p.status}
        {p.updated_at ? ` · ${new Date(p.updated_at).toLocaleString()}` : ""}
      </p>
    </div>
  );
}

export function SpeakerProfileCards() {
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["speaker-profiles"],
    queryFn: () => apiFetch<ProfilesResponse>("/api/v1/speaker-profiles"),
  });

  const distill = useMutation({
    mutationFn: ({ role, name }: { role: string; name: string }) =>
      apiFetch<SpeakerProfileData>(`/api/v1/speaker-profiles/distill/${role}?display_name=${encodeURIComponent(name)}`, {
        method: "POST",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["speaker-profiles"] });
    },
  });

  const profiles = data?.profiles ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>🎭 人物画像</CardTitle>
        <p className="text-[10px] text-[var(--muted)] font-normal">
          通过 LLM 蒸馏双方的说话风格、口头禅、情绪模式等特征
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading && <p className="text-xs text-[var(--muted)]">加载中…</p>}

        {/* 已有画像 */}
        {profiles.map((p) => (
          <div key={p.id} className="border border-[var(--border)] rounded-xl p-4 bg-[var(--warm)]/50">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-[var(--fg)]">
                {p.display_name}
                <span className="text-[10px] text-[var(--muted)] ml-2 font-normal">
                  ({p.speaker_role === "owner" ? "你" : "对方"})
                </span>
              </h3>
              <Button
                type="button"
                variant="outline"
                className="text-xs h-7 px-2"
                disabled={distill.isPending}
                onClick={() => distill.mutate({ role: p.speaker_role, name: p.display_name })}
              >
                {distill.isPending ? "蒸馏中…" : "重新生成"}
              </Button>
            </div>
            <ProfileContent p={p} />
          </div>
        ))}

        {/* 无画像：生成按钮 */}
        {!isLoading && profiles.length === 0 && (
          <div className="text-center space-y-2 py-4">
            <p className="text-xs text-[var(--muted)]">尚未蒸馏人物画像</p>
            <div className="flex justify-center gap-2">
              <Button
                type="button"
                variant="outline"
                className="text-xs"
                disabled={distill.isPending}
                onClick={() => distill.mutate({ role: "owner", name: "我" })}
              >
                蒸馏我的画像
              </Button>
              <Button
                type="button"
                variant="outline"
                className="text-xs"
                disabled={distill.isPending}
                onClick={() => distill.mutate({ role: "partner", name: "对方" })}
              >
                蒸馏对方的画像
              </Button>
            </div>
          </div>
        )}

        {/* 只生成了一个，显示另一个的按钮 */}
        {!isLoading && profiles.length === 1 && (
          <div className="text-center pt-1">
            <Button
              type="button"
              variant="ghost"
              className="text-xs"
              disabled={distill.isPending}
              onClick={() => distill.mutate({
                role: profiles[0].speaker_role === "owner" ? "partner" : "owner",
                name: profiles[0].speaker_role === "owner" ? "对方" : "我",
              })}
            >
              蒸馏{profiles[0].speaker_role === "owner" ? "对方" : "自己"}的画像
            </Button>
          </div>
        )}

        {distill.isPending && (
          <p className="text-xs text-[var(--muted)] animate-pulse">正在蒸馏中，这可能需要 10-30 秒…</p>
        )}
      </CardContent>
    </Card>
  );
}
