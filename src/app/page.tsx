"use client";

import { useEffect, useState } from "react";
import { AuditTimeline } from "@/app/components/AuditTimeline";
import { ContextSnapshotCard } from "@/app/components/ContextSnapshotCard";
import { ContextReceiptCard } from "@/app/components/ContextReceiptCard";
import { EventInspector } from "@/app/components/EventInspector";
import { ReviewComposer } from "@/app/components/ReviewComposer";
import { RunList } from "@/app/components/RunList";
import { TaskList } from "@/app/components/TaskList";
import { TaskOverview } from "@/app/components/TaskOverview";
import { fetchSession, subscribeToAuditStream } from "@/app/lib/audit-api";
import { getTask, listTasks, listUnboundRuns } from "@/app/lib/harness-api";
import type { AuditEvent, AuditSession } from "@/app/lib/audit-types";
import type { TaskContract, UnboundRun } from "@/app/lib/harness-types";

export default function Home() {
  const [tasks, setTasks] = useState<TaskContract[]>([]); const [unbound, setUnbound] = useState<UnboundRun[]>([]);
  const [task, setTask] = useState<TaskContract | null>(null); const [session, setSession] = useState<AuditSession | null>(null); const [event, setEvent] = useState<AuditEvent | null>(null); const [error, setError] = useState(""); const [connected, setConnected] = useState(false);

  useEffect(() => { void (async () => { try { const [nextTasks, nextUnbound] = await Promise.all([listTasks(), listUnboundRuns()]); setTasks(nextTasks); setUnbound(nextUnbound); if (nextTasks[0]) await selectTask(nextTasks[0].task_id); } catch (cause) { setError(cause instanceof Error ? cause.message : "无法连接本地服务"); } })(); }, []);
  useEffect(() => subscribeToAuditStream(session?.session_id ?? null, message => { setConnected(true); if (session?.session_id === message.event.session_id) setSession(current => current ? { ...current, events: [...current.events, message.event] } : current); if (message.run) void selectTask(message.run.task_id); }, () => setConnected(false)), [session?.session_id]);
  async function selectTask(id: string) { try { setError(""); setTask(await getTask(id)); } catch (cause) { setError(cause instanceof Error ? cause.message : "无法读取 Task"); } }
  async function selectSession(id: string) { try { setError(""); const value = await fetchSession(id); setSession(value); setEvent(value.events.at(-1) ?? null); } catch (cause) { setError(cause instanceof Error ? cause.message : "无法读取运行证据"); } }
  return <main className="min-h-screen bg-zinc-50 text-zinc-950 dark:bg-black dark:text-zinc-50"><header className="border-b border-zinc-200 bg-white/90 px-4 py-4 dark:border-zinc-800 dark:bg-black/80"><div className="mx-auto flex max-w-[1600px] items-center justify-between"><div><h1 className="text-lg font-bold">EvolveTrace</h1><p className="text-xs text-zinc-500">Task, context, and evidence for coding-agent review</p></div><span className="text-xs text-zinc-500"><i className={`mr-2 inline-block h-2 w-2 rounded-full ${connected ? "bg-emerald-500" : "bg-zinc-300"}`} />{connected ? "实时监听中" : "本地服务"}</span></div></header><div className="mx-auto grid min-h-[calc(100vh-73px)] max-w-[1600px] lg:grid-cols-[260px_minmax(400px,1fr)_minmax(300px,.8fr)]"><TaskList tasks={tasks} unboundRuns={unbound} selectedTaskId={task?.task_id ?? null} onSelectTask={id => void selectTask(id)} onSelectUnbound={id => void selectSession(id)} /><section className="min-w-0 border-b border-zinc-200 p-4 dark:border-zinc-800 sm:p-6 lg:border-b-0">{error && <p className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950/40 dark:text-red-200">{error}</p>}<TaskOverview task={task} /><ContextSnapshotCard task={task} /><ContextReceiptCard receipts={task?.context_receipts ?? []} /><RunList runs={task?.runs ?? []} selectedId={session?.session_id ?? null} onSelect={id => void selectSession(id)} />{session && <div className="mt-5"><AuditTimeline events={session.events} selectedId={event?.event_id ?? null} onSelect={setEvent} /></div>}</section><aside className="flex min-h-0 flex-col bg-white dark:bg-zinc-950"><div className="min-h-0 flex-1 overflow-y-auto"><EventInspector event={event} /></div><ReviewComposer event={event} /></aside></div></main>;
}
