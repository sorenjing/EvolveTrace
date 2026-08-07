"use client";

import { useEffect, useState } from "react";
import { AuditTimeline } from "@/app/components/AuditTimeline";
import { EventInspector } from "@/app/components/EventInspector";
import { ReviewComposer } from "@/app/components/ReviewComposer";
import { SessionList } from "@/app/components/SessionList";
import { SessionSummary } from "@/app/components/SessionSummary";
import { fetchSession, fetchSessions, subscribeToAuditStream } from "@/app/lib/audit-api";
import type { AuditEvent, AuditSession, AuditSessionSummary } from "@/app/lib/audit-types";

export default function Home() {
  const [sessions, setSessions] = useState<AuditSessionSummary[]>([]);
  const [session, setSession] = useState<AuditSession | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<AuditEvent | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        setError("");
        const nextSessions = await fetchSessions();
        setSessions(nextSessions);
        if (nextSessions.length > 0) await selectSession(nextSessions[0].session_id);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "无法连接本地审计服务");
      }
    })();
  }, []);

  useEffect(() => {
    const close = subscribeToAuditStream(
      session?.session_id ?? null,
      (message) => {
        setConnected(true);
        setSessions((current) => {
          const existing = current.find((item) => item.session_id === message.event.session_id);
          if (!existing) return current;
          return current.map((item) => item.session_id === message.event.session_id ? { ...item, event_count: item.event_count + 1, tool_call_count: item.tool_call_count + (message.event.tool_name ? 1 : 0), risk_count: item.risk_count + message.risk_findings.length, last_seen: message.event.timestamp } : item);
        });
        if (session?.session_id === message.event.session_id) {
          setSession((current) => current ? { ...current, events: [...current.events, message.event], event_count: current.event_count + 1, tool_call_count: current.tool_call_count + (message.event.tool_name ? 1 : 0), risk_count: current.risk_count + message.risk_findings.length, last_seen: message.event.timestamp } : current);
        }
      },
      () => setConnected(false),
    );
    return close;
  }, [session?.session_id]);

  async function selectSession(sessionId: string) {
    try {
      const nextSession = await fetchSession(sessionId);
      setSession(nextSession);
      setSelectedEvent(nextSession.events.at(-1) ?? null);
      setSelectedId(nextSession.events.at(-1)?.event_id ?? null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "无法读取会话");
    }
  }

  return (
    <main className="min-h-screen bg-zinc-50 text-zinc-950 dark:bg-black dark:text-zinc-50">
      <header className="border-b border-zinc-200 bg-white/90 px-4 py-4 backdrop-blur dark:border-zinc-800 dark:bg-black/80 sm:px-6">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-teal-500" /><h1 className="text-lg font-bold tracking-tight">EvolveTrace</h1></div>
            <p className="mt-1 text-xs text-zinc-500">Local review and observability for coding agents</p>
          </div>
          <div className="flex items-center gap-3 text-xs text-zinc-500"><span className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-500" : "bg-zinc-300"}`} />{connected ? "实时监听中" : "等待本地事件"}</div>
        </div>
      </header>
      <div className="mx-auto grid min-h-[calc(100vh-77px)] max-w-[1600px] lg:grid-cols-[260px_minmax(360px,1fr)_minmax(300px,0.8fr)]">
        <SessionList sessions={sessions} selectedId={session?.session_id ?? null} onSelect={(id) => void selectSession(id)} />
        <section className="min-w-0 border-b border-zinc-200 p-4 dark:border-zinc-800 sm:p-6 lg:border-b-0">
          {error && <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">{error}</div>}
          {session ? <><div className="mb-5"><p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-teal-600 dark:text-teal-400">Review workspace</p><h2 className="mt-1 truncate text-xl font-semibold">{session.cwd || session.session_id}</h2><p className="mt-1 text-xs text-zinc-500">按证据复盘 Codex 的执行路径，而不是猜测隐藏思维。</p></div><SessionSummary session={session} /><div className="mt-5"><AuditTimeline events={session.events} selectedId={selectedId} onSelect={(event) => { setSelectedEvent(event); setSelectedId(event.event_id); }} /></div></> : <EmptyState />}
        </section>
        <aside className="flex min-h-0 flex-col bg-white dark:bg-zinc-950"><div className="min-h-0 flex-1 overflow-y-auto"><EventInspector event={selectedEvent} /></div><ReviewComposer event={selectedEvent} /></aside>
      </div>
    </main>
  );
}

function EmptyState() {
  return <div className="flex min-h-[50vh] flex-col items-center justify-center text-center"><div className="rounded-2xl border border-dashed border-zinc-300 p-8 dark:border-zinc-700"><p className="text-lg font-semibold">等待第一条执行轨迹</p><p className="mt-2 max-w-sm text-sm leading-6 text-zinc-500">启动本地后端并启用 EvolveTrace for Codex，然后执行一个任务。每一步会在这里形成可审查的工程记录。</p></div></div>;
}
