"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch } from "@/lib/api";

type MemberBrief = {
  user_id: number;
  display_name: string;
  chat_aliases: string[];
};

type SettingsCouple = {
  id: number;
  name: string;
  timezone: string;
  status: string;
  openclaw_webhook_url: string;
  openclaw_token_hint: string;
  owner: MemberBrief;
  partner: MemberBrief | null;
  bot_name?: string | null;
  bot_persona?: string | null;
  day_start_hour?: number;
};

type Me = {
  id: number;
  email: string;
  display_name: string;
  role: string;
  chat_aliases: string[];
};

function aliasesToText(aliases: string[] | undefined) {
  return (aliases ?? []).join("\n");
}

function textToAliases(text: string) {
  return text
    .split(/\r?\n/)
    .map((s) => s.trim())
    .filter(Boolean);
}

export default function SettingsPage() {
  const qc = useQueryClient();
  const [displayName, setDisplayName] = useState("");
  const [aliasesText, setAliasesText] = useState("");
  const [accountMsg, setAccountMsg] = useState<string | null>(null);

  const [coupleName, setCoupleName] = useState("");
  const [coupleMsg, setCoupleMsg] = useState<string | null>(null);

  const [botNameInput, setBotNameInput] = useState("");
  const [botPersonaInput, setBotPersonaInput] = useState("");
  const [botMsg, setBotMsg] = useState<string | null>(null);

  const [dayStartHour, setDayStartHour] = useState(6);
  const [dayBoundaryMsg, setDayBoundaryMsg] = useState<string | null>(null);

  const { data, refetch: refetchCouple } = useQuery({
    queryKey: ["settings-couple"],
    queryFn: () => apiFetch<SettingsCouple>("/api/v1/settings/couple"),
  });

  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<Me>("/api/v1/auth/me"),
  });

  useEffect(() => {
    if (me?.display_name != null) {
      setDisplayName(me.display_name);
      setAliasesText(aliasesToText(me.chat_aliases));
    }
  }, [me?.display_name, me?.chat_aliases]);

  useEffect(() => {
    if (data?.name != null) {
      setCoupleName(data.name);
    }
    setBotNameInput(data?.bot_name || "");
    setBotPersonaInput(data?.bot_persona || "");
    setDayStartHour(data?.day_start_hour ?? 6);
  }, [data?.name, data?.bot_name, data?.bot_persona]);

  const saveProfile = useMutation({
    mutationFn: (payload: { display_name: string; chat_aliases: string[] }) =>
      apiFetch<Me>("/api/v1/auth/me", {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["me"] });
      refetchCouple();
      setAccountMsg("已保存。");
    },
    onError: (e: Error) => {
      setAccountMsg(e.message);
    },
  });

  const saveCoupleName = useMutation({
    mutationFn: (name: string) =>
      apiFetch<SettingsCouple>("/api/v1/settings/couple", {
        method: "PATCH",
        body: JSON.stringify({ name }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings-couple"] });
      setCoupleMsg("空间名称已保存。");
    },
    onError: (e: Error) => {
      setCoupleMsg(e.message);
    },
  });

  const saveBotSettings = useMutation({
    mutationFn: (payload: { bot_name?: string; bot_persona?: string }) =>
      apiFetch<SettingsCouple>("/api/v1/settings/couple/bot", {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings-couple"] });
      setBotMsg("机器人设置已保存。");
    },
    onError: (e: Error) => {
      setBotMsg(e.message);
    },
  });

  const saveDayBoundary = useMutation({
    mutationFn: (hour: number) =>
      apiFetch<SettingsCouple>("/api/v1/settings/couple/day-boundary", {
        method: "PATCH",
        body: JSON.stringify({ day_start_hour: hour }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings-couple"] });
      setDayBoundaryMsg("已保存。修改后新上传的消息将按新的分界线归日。");
    },
    onError: (e: Error) => {
      setDayBoundaryMsg(e.message);
    },
  });

  const rebuildDayKeys = useMutation({
    mutationFn: () =>
      apiFetch<{ updated: number; affected_days: number }>("/api/v1/messages/rebuild-day-keys", {
        method: "POST",
      }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["days"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      setDayBoundaryMsg(`重建完成：${r.updated} 条消息重新归日，涉及 ${r.affected_days} 天。`);
    },
    onError: (e: Error) => {
      setDayBoundaryMsg(e.message);
    },
  });

  const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const otherMember: MemberBrief | null =
    me && data
      ? me.id === data.owner.user_id
        ? data.partner
        : me.id === data.partner?.user_id
          ? data.owner
          : null
      : null;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">系统设置</h1>

      <Card>
        <CardHeader>
          <CardTitle>情侣空间</CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-4 max-w-lg">
          <p className="text-[var(--muted)] leading-relaxed">
            空间名称对两人可见；时区影响上传记录按日归档。
          </p>
          <div className="space-y-2">
            <Label htmlFor="couple-name">空间名称</Label>
            <Input
              id="couple-name"
              value={coupleName}
              onChange={(e) => {
                setCoupleName(e.target.value);
                setCoupleMsg(null);
              }}
              maxLength={128}
            />
          </div>
          <p>
            <span className="text-[var(--muted)]">时区</span>：{data?.timezone}
          </p>
          <p>
            <span className="text-[var(--muted)]">状态</span>：{data?.status}
          </p>
          <Button
            type="button"
            disabled={
              saveCoupleName.isPending ||
              !coupleName.trim() ||
              coupleName.trim() === data?.name
            }
            onClick={() => saveCoupleName.mutate(coupleName.trim())}
          >
            {saveCoupleName.isPending ? "保存中…" : "保存空间名称"}
          </Button>
          {coupleMsg && (
            <p className="text-sm whitespace-pre-wrap break-words">{coupleMsg}</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>每日分界线</CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-4 max-w-lg">
          <p className="text-[var(--muted)] leading-relaxed">
            设置「一天」的起始时间。比如设为 6 点，则凌晨 0:00-5:59 的消息归属前一天，适合经常熬夜聊天的情侣。
          </p>
          <div className="space-y-2">
            <Label htmlFor="day-start">每天从几点开始</Label>
            <div className="flex items-center gap-3">
              <select
                id="day-start"
                className="rounded-xl border border-[var(--border)] bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-rose-200/40"
                value={dayStartHour}
                onChange={(e) => { setDayStartHour(Number(e.target.value)); setDayBoundaryMsg(null); }}
              >
                {[0,1,2,3,4,5,6,7,8,9,10,11,12].map(h => (
                  <option key={h} value={h}>{h === 0 ? "0:00（午夜）" : `${h}:00`}</option>
                ))}
              </select>
              <span className="text-xs text-[var(--muted)]">
                即 {dayStartHour}:00 ~ 次日 {dayStartHour}:00 为一天
              </span>
            </div>
          </div>
          <Button
            type="button"
            disabled={saveDayBoundary.isPending || dayStartHour === (data?.day_start_hour ?? 6)}
            onClick={() => saveDayBoundary.mutate(dayStartHour)}
          >
            {saveDayBoundary.isPending ? "保存中…" : "保存分界线设置"}
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={rebuildDayKeys.isPending}
            onClick={() => {
              if (confirm("将根据当前分界线设置重新归日所有已有消息，可能需要一段时间。确认？")) {
                rebuildDayKeys.mutate();
              }
            }}
          >
            {rebuildDayKeys.isPending ? "重建中…" : "重建已有消息的按日分组"}
          </Button>
          {dayBoundaryMsg && <p className="text-xs text-[var(--muted)]">{dayBoundaryMsg}</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>我的账号与微信昵称</CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-4 max-w-lg">
          <p className="text-[var(--muted)] leading-relaxed">
            <strong>显示名</strong>用于站内展示；<strong>微信昵称</strong>可填多个（每行一个），需与导出记录里的发言人名称<strong>完全一致</strong>，「按日聊天」才会把你的消息放到右侧绿气泡。
          </p>
          {me && (
            <p>
              <span className="text-[var(--muted)]">邮箱</span>：{me.email}
            </p>
          )}
          <div className="space-y-2">
            <Label htmlFor="display-name">显示名</Label>
            <Input
              id="display-name"
              value={displayName}
              onChange={(e) => {
                setDisplayName(e.target.value);
                setAccountMsg(null);
              }}
              maxLength={128}
              autoComplete="nickname"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="wx-aliases">微信昵称（每行一个，最多约 40 条）</Label>
            <textarea
              id="wx-aliases"
              className="flex min-h-[120px] w-full rounded-xl border border-[var(--border)] bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--accent)]/30"
              value={aliasesText}
              onChange={(e) => {
                setAliasesText(e.target.value);
                setAccountMsg(null);
              }}
              placeholder={"例如：\n张三\nwxid_占位示例"}
              spellCheck={false}
            />
          </div>
          <Button
            type="button"
            disabled={saveProfile.isPending || !displayName.trim()}
            onClick={() =>
              saveProfile.mutate({
                display_name: displayName.trim(),
                chat_aliases: textToAliases(aliasesText),
              })
            }
          >
            {saveProfile.isPending ? "保存中…" : "保存我的资料"}
          </Button>
          {accountMsg && (
            <p className="text-sm whitespace-pre-wrap break-words">{accountMsg}</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>对方名片（只读）</CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-3 max-w-lg text-[var(--muted)]">
          {!otherMember ? (
            <p>当前空间尚未绑定另一半账号，或未设置对方用户。</p>
          ) : (
            <>
              <p>
                <span className="text-[var(--muted)]">显示名</span>：{otherMember.display_name}
              </p>
              <div>
                <p className="mb-1">对方已保存的微信昵称：</p>
                {otherMember.chat_aliases.length === 0 ? (
                  <p className="text-xs">（无，需对方登录后在同样位置填写）</p>
                ) : (
                  <ul className="list-disc pl-5 text-[var(--fg)] space-y-0.5">
                    {otherMember.chat_aliases.map((a) => (
                      <li key={a}>{a}</li>
                    ))}
                  </ul>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>智能助理设置</CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-4 max-w-lg">
          <p className="text-[var(--muted)] leading-relaxed">
            自定义智能机器人的名字和性格。留空则使用默认设置（小恋）。
          </p>
          <div className="space-y-2">
            <Label htmlFor="bot-name">机器人名字</Label>
            <Input
              id="bot-name"
              value={botNameInput}
              onChange={(e) => { setBotNameInput(e.target.value); setBotMsg(null); }}
              placeholder="小恋"
              maxLength={64}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="bot-persona">性格描述</Label>
            <textarea
              id="bot-persona"
              className="w-full min-h-[80px] rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--ring)]"
              value={botPersonaInput}
              onChange={(e) => { setBotPersonaInput(e.target.value); setBotMsg(null); }}
              placeholder="温暖贴心的恋爱助理，了解你们的所有聊天记录…"
              maxLength={1024}
            />
            <p className="text-xs text-[var(--muted)]">{botPersonaInput.length}/1024</p>
          </div>
          <Button
            onClick={() => saveBotSettings.mutate({ bot_name: botNameInput, bot_persona: botPersonaInput })}
            disabled={saveBotSettings.isPending}
          >
            {saveBotSettings.isPending ? "保存中…" : "保存机器人设置"}
          </Button>
          {botMsg && <p className="text-xs text-[var(--muted)]">{botMsg}</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>OpenClaw（占位）</CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-3 text-[var(--muted)] leading-relaxed">
          <p>在 OpenClaw 中配置 Webhook URL（需加上你的 API 域名）：</p>
          <code className="block p-3 rounded-xl bg-black/[0.04] dark:bg-white/[0.06] text-[var(--fg)] break-all">
            {base}
            {data?.openclaw_webhook_url}
          </code>
          <p>请求头：</p>
          <code className="block p-3 rounded-xl bg-black/[0.04] dark:bg-white/[0.06] text-[var(--fg)]">
            Authorization: Bearer &lt;OPENCLAW_BEARER_TOKEN&gt;
          </code>
          <p>提示：{data?.openclaw_token_hint}</p>
        </CardContent>
      </Card>
    </div>
  );
}
