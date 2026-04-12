"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch, smartBotStream, type SmartBotStreamEvent } from "@/lib/api";
import { Button } from "@/components/ui/button";

type Message = {
  role: "user" | "bot";
  content: string;
  skill?: string;
  skillLabel?: string;
  status?: string;
  citations?: unknown[];
  sqlQuery?: string;
  sqlRowCount?: number;
};

type CoupleSettings = {
  id: number;
  bot_name?: string | null;
  bot_persona?: string | null;
};

const STORAGE_KEY = "lr_chat_history";
const MAX_PERSIST = 40; // 最多持久化 40 条

const SKILL_COLORS: Record<string, string> = {
  chat_search: "bg-rose-50 text-rose-600 dark:bg-rose-900/20 dark:text-rose-300",
  data_query: "bg-violet-50 text-violet-600 dark:bg-violet-900/20 dark:text-violet-300",
  emotion_analysis: "bg-pink-50 text-pink-600 dark:bg-pink-900/20 dark:text-pink-300",
  advice: "bg-amber-50 text-amber-600 dark:bg-amber-900/20 dark:text-amber-300",
  general_chat: "bg-stone-50 text-stone-500 dark:bg-stone-800/20 dark:text-stone-400",
};

function loadMessages(): Message[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr.filter((m: Message) => m.content && !m.status) : [];
  } catch { return []; }
}

function saveMessages(msgs: Message[]) {
  if (typeof window === "undefined") return;
  const clean = msgs.filter(m => m.content && !m.status).slice(-MAX_PERSIST);
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(clean)); } catch {}
}

export function SmartBotPanel() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>(() => loadMessages());
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [botName, setBotName] = useState("小恋");
  const scrollRef = useRef<HTMLDivElement>(null);
  const msgsRef = useRef(messages);

  useEffect(() => { msgsRef.current = messages; }, [messages]);

  // 持久化到 localStorage
  useEffect(() => {
    if (messages.length > 0 && !busy) saveMessages(messages);
  }, [messages, busy]);

  const { data: settings } = useQuery({
    queryKey: ["settings-couple"],
    queryFn: () => apiFetch<CoupleSettings>("/api/v1/settings/couple"),
  });

  useEffect(() => {
    if (settings?.bot_name) setBotName(settings.bot_name);
  }, [settings]);

  const scroll = useCallback(() => {
    setTimeout(() => scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" }), 50);
  }, []);

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    setBusy(true);
    setStatus(null);
    setInput("");

    const history = msgsRef.current
      .filter(m => m.content && !m.status)
      .slice(-20)
      .map(m => ({ role: m.role, content: m.content }));

    setMessages(prev => [...prev, { role: "user", content: text }]);
    scroll();
    setMessages(prev => [...prev, { role: "bot", content: "", status: "思考中…" }]);

    // 构建 identity —— 空字符串不传，让后端用默认
    const identity = settings?.bot_name
      ? { name: settings.bot_name, persona: settings.bot_persona || "" }
      : undefined;

    try {
      await smartBotStream(
        { question: text, identity, conversation_history: history },
        (ev: SmartBotStreamEvent) => {
          if (ev.event === "meta") {
            setBotName(ev.bot_name);
            setMessages(prev => { const u = [...prev]; u[u.length-1] = { ...u[u.length-1], skill: ev.skill, skillLabel: ev.skill_label }; return u; });
          }
          if (ev.event === "status") {
            setStatus(ev.message);
            setMessages(prev => { const u = [...prev]; u[u.length-1] = { ...u[u.length-1], status: ev.message }; return u; });
          }
          if (ev.event === "token") {
            setMessages(prev => { const u = [...prev]; const l = u.length-1; u[l] = { ...u[l], content: (u[l].content||"")+ev.text, status: undefined }; return u; });
            scroll();
          }
          if (ev.event === "done") {
            setMessages(prev => {
              const u = [...prev]; const l = u.length-1;
              u[l] = { ...u[l], status: undefined, citations: ev.citations, sqlQuery: ev.sql_query, sqlRowCount: ev.sql_row_count, skill: ev.skill_used, skillLabel: ev.skill_label };
              return u;
            });
          }
        },
      );
    } catch (e) {
      setMessages(prev => { const u = [...prev]; u[u.length-1] = { ...u[u.length-1], content: `请求失败：${e instanceof Error ? e.message : "未知"}`, status: undefined }; return u; });
    } finally {
      setBusy(false);
      setStatus(null);
      scroll();
    }
  }

  function clearHistory() {
    setMessages([]);
    localStorage.removeItem(STORAGE_KEY);
  }

  return (
    <div className="flex flex-col h-[560px] rounded-3xl border border-[var(--border)] bg-[var(--card)] shadow-sm overflow-hidden">
      {/* 头部 */}
      <div className="px-5 py-3.5 border-b border-[var(--border)] bg-gradient-to-r from-rose-50/80 to-pink-50/60 dark:from-rose-950/20 dark:to-pink-950/10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-rose-400 to-pink-500 flex items-center justify-center text-white text-sm font-medium shadow-sm">
              {botName[0]}
            </div>
            <div>
              <h3 className="text-sm font-semibold text-[var(--fg)]">{botName}</h3>
              <p className="text-[10px] text-[var(--muted)]">
                聊天搜索 · 数据统计 · 情感分析 · 恋爱建议
              </p>
            </div>
          </div>
          {messages.length > 0 && (
            <button onClick={clearHistory} className="text-[10px] text-[var(--muted)] hover:text-rose-500 transition-colors px-2 py-1 rounded-lg hover:bg-rose-50 dark:hover:bg-rose-900/20">
              清空
            </button>
          )}
        </div>
      </div>

      {/* 消息区 */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {messages.length === 0 && (
          <div className="text-center py-12 space-y-4">
            <div className="w-14 h-14 mx-auto rounded-full bg-gradient-to-br from-rose-400 to-pink-500 flex items-center justify-center text-white text-xl shadow-lg">
              {botName[0]}
            </div>
            <div>
              <p className="text-sm text-[var(--fg)] font-medium">你好呀，我是{botName}</p>
              <p className="text-xs text-[var(--muted)] mt-1">你们的专属恋爱助理，有什么想问的？</p>
            </div>
            <div className="flex flex-wrap justify-center gap-2 mt-3">
              {["上周我们聊了什么？", "这个月发了多少条消息？", "我们最近感情怎么样？", "她说过想吃什么？"].map(q => (
                <button
                  key={q}
                  onClick={() => { setInput(q); }}
                  className="text-xs px-3 py-1.5 rounded-full border border-rose-200 text-rose-600 hover:bg-rose-50 dark:border-rose-800 dark:text-rose-300 dark:hover:bg-rose-900/20 transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[80%] text-sm ${
              msg.role === "user"
                ? "bg-gradient-to-r from-rose-500 to-pink-500 text-white rounded-2xl rounded-br-sm px-4 py-2.5 shadow-sm"
                : "bg-[var(--bg)] border border-[var(--border)] rounded-2xl rounded-bl-sm px-4 py-2.5"
            }`}>
              {msg.role === "bot" && msg.skillLabel && (
                <span className={`inline-block text-[10px] px-2 py-0.5 rounded-full mb-1.5 ${SKILL_COLORS[msg.skill || ""] || SKILL_COLORS.general_chat}`}>
                  {msg.skillLabel}
                </span>
              )}
              {msg.status && <p className="text-xs text-[var(--muted)] animate-pulse">{msg.status}</p>}
              {msg.content && <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>}
              {msg.sqlQuery && (
                <details className="mt-2 text-xs">
                  <summary className="cursor-pointer text-[var(--muted)] hover:text-[var(--fg)]">SQL ({msg.sqlRowCount} 条)</summary>
                  <pre className="mt-1 overflow-auto bg-black/5 dark:bg-white/5 rounded-lg p-2 text-[10px]">{msg.sqlQuery}</pre>
                </details>
              )}
              {msg.citations && msg.citations.length > 0 && (
                <details className="mt-2 text-xs">
                  <summary className="cursor-pointer text-[var(--muted)] hover:text-[var(--fg)]">引用 ({msg.citations.length})</summary>
                  <pre className="mt-1 max-h-28 overflow-auto bg-black/5 dark:bg-white/5 rounded-lg p-2 text-[10px]">{JSON.stringify(msg.citations, null, 2)}</pre>
                </details>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* 状态 */}
      {status && (
        <div className="px-5 py-1">
          <p className="text-[10px] text-rose-500 animate-pulse">{status}</p>
        </div>
      )}

      {/* 输入区 */}
      <div className="px-4 py-3 border-t border-[var(--border)] bg-[var(--bg)]/50">
        <div className="flex gap-2 items-end">
          <textarea
            className="flex-1 min-h-[40px] max-h-[100px] rounded-2xl border border-[var(--border)] bg-[var(--card)] px-4 py-2.5 text-sm outline-none focus:border-rose-300 focus:ring-2 focus:ring-rose-200/50 dark:focus:border-rose-700 dark:focus:ring-rose-800/30 resize-none placeholder:text-[var(--muted)]/60 transition-all"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(); } }}
            placeholder="输入你的问题…"
            disabled={busy}
            rows={1}
          />
          <button
            onClick={() => void send()}
            disabled={busy || !input.trim()}
            className="w-9 h-9 rounded-full bg-gradient-to-r from-rose-500 to-pink-500 text-white flex items-center justify-center disabled:opacity-40 hover:shadow-md transition-all shrink-0"
          >
            {busy ? (
              <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M22 2L11 13"/><path d="M22 2L15 22L11 13L2 9L22 2Z"/></svg>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
