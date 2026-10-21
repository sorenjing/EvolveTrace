"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AuditTimeline } from "@/app/components/AuditTimeline";
import { ContextSnapshotCard } from "@/app/components/ContextSnapshotCard";
import { ContextReceiptCard } from "@/app/components/ContextReceiptCard";
import { EventInspector } from "@/app/components/EventInspector";
import { ReviewComposer } from "@/app/components/ReviewComposer";
import { RunList } from "@/app/components/RunList";
import { TaskList } from "@/app/components/TaskList";
import { TaskOverview } from "@/app/components/TaskOverview";
import { EvaluationPanel } from "@/app/components/EvaluationPanel";
import { RunWorkflow } from "@/app/components/RunWorkflow";
import { ActivityPanel } from "@/app/components/ActivityPanel";
import { buildAuditSteps } from "@/app/lib/audit-flow";
import { fetchSession, subscribeToAuditStream } from "@/app/lib/audit-api";
import { recoverSession } from "@/app/lib/audit-recovery";
import { getTask, listTasks, listUnboundRuns } from "@/app/lib/harness-api";
import type { AuditSession } from "@/app/lib/audit-types";
import type { TaskContract, UnboundRun } from "@/app/lib/harness-types";
import type { ActivityProject } from "@/app/lib/activity-types";
import { projectForSession } from "@/app/lib/activity-navigation";

export default function Home() {
  const [tasks, setTasks] = useState<TaskContract[]>([]);
  const [projects, setProjects] = useState<ActivityProject[]>([]);
  const [projectId, setProjectId] = useState<string | null>(null);
  const projectIndex = useRef<ActivityProject[]>([]);
  const selectedProject = useRef<string | null>(null);
  const [unbound, setUnbound] = useState<UnboundRun[]>([]);
  const [task, setTask] = useState<TaskContract | null>(null);
  const [session, setSession] = useState<AuditSession | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [timelineScope, setTimelineScope] = useState<{ sessionId: string; projectId: string | null; eventIds: string[] } | null>(null);
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [recoveryError, setRecoveryError] = useState("");
  const [connected, setConnected] = useState(false);
  const [activityRevision, setActivityRevision] = useState(0);
  const selectedSession = useRef<string | null>(null);
  const selectedTask = useRef<string | null>(null);
  const navigation = useRef(0);
  const scopedEvents = useMemo(() => {
    if (!session) return [];
    if (!projectId) return session.events;
    if (timelineScope?.sessionId !== session.session_id || timelineScope.projectId !== projectId) return [];
    const ids = new Set(timelineScope.eventIds);
    return session.events.filter(event => ids.has(event.event_id));
  }, [session, projectId, timelineScope]);
  const steps = useMemo(() => buildAuditSteps(scopedEvents), [scopedEvents]);
  const selectedStep = steps.find(step => step.id === selectedStepId) ?? steps.at(-1) ?? null;

  const updateProjects = useCallback((value: ActivityProject[]) => {
    projectIndex.current = value;
    setProjects(value);
  }, []);

  const updateScopeEvents = useCallback((id: string, pid: string | null, eventIds: string[]) => {
    if (selectedSession.current === id && selectedProject.current === pid) setTimelineScope({ sessionId: id, projectId: pid, eventIds });
  }, []);

  function selectProject(id: string | null) {
    ++navigation.current;
    selectedProject.current = id;
    selectedTask.current = null;
    selectedSession.current = null;
    setSessionId(null);
    setProjectId(id);
    setTask(null);
    setSession(null);
    setSelectedStepId(null);
    setError("");
    setRecoveryError("");
  }

  const selectSession = useCallback(async (id: string, owner: TaskContract | null = null) => {
    const version = ++navigation.current;
    const matchingTask = owner?.runs?.some(run => run.task_id === owner.task_id && run.session_id === id) ? owner : null;
    selectedTask.current = matchingTask?.task_id ?? null;
    selectedSession.current = id;
    setSessionId(id);
    selectedProject.current = projectForSession(projectIndex.current, id, selectedProject.current);
    setProjectId(selectedProject.current);
    setTask(matchingTask);
    setSession(null);
    setSelectedStepId(null);
    try {
      setError("");
      const value = await fetchSession(id);
      if (navigation.current !== version) return;
      setSession(value);
      setSelectedStepId(buildAuditSteps(value.events).at(-1)?.id ?? null);
    } catch (cause) { if (navigation.current === version) setError(cause instanceof Error ? cause.message : "无法读取运行证据"); }
  }, []);

  const selectTask = useCallback(async (id: string) => {
    const version = ++navigation.current;
    selectedTask.current = id;
    selectedSession.current = null;
    setSessionId(null);
    selectedProject.current = null;
    setProjectId(null);
    setTask(null);
    setSession(null);
    setSelectedStepId(null);
    try {
      setError("");
      const value = await getTask(id);
      if (navigation.current !== version) return;
      setTask(value);
      const initial = value.runs?.find(run => run.session_id);
      if (initial?.session_id) await selectSession(initial.session_id, value);
    }
    catch (cause) { if (navigation.current === version) setError(cause instanceof Error ? cause.message : "无法读取 Task"); }
  }, [selectSession]);

  useEffect(() => {
    const version = navigation.current;
    let cancelled = false;
    void (async () => {
      try {
        const [nextTasks, nextUnbound] = await Promise.all([listTasks(), listUnboundRuns()]);
        if (cancelled || navigation.current !== version) return;
        setTasks(nextTasks);
        setUnbound(nextUnbound);
      } catch (cause) {
        if (!cancelled && navigation.current === version) setError(cause instanceof Error ? cause.message : "无法连接本地服务");
      }
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    let recovering = false;
    let recoverAgain = false;
    const sessionId = session?.session_id;
    async function recover() {
      if (recovering) { recoverAgain = true; return; }
      recovering = true;
      try {
        do {
          recoverAgain = false;
          const taskId = selectedTask.current;
          const version = navigation.current;
          const [nextTasks, nextUnbound, snapshot, refreshedTask] = await Promise.all([
            listTasks(), listUnboundRuns(), sessionId ? fetchSession(sessionId) : null,
            taskId ? getTask(taskId) : null,
          ]);
          if (cancelled) return;
          setTasks(nextTasks);
          setUnbound(nextUnbound);
          if (snapshot && navigation.current === version && selectedSession.current === sessionId) setSession(current => recoverSession(snapshot, current));
          if (refreshedTask && navigation.current === version && selectedTask.current === taskId) setTask(refreshedTask);
          setRecoveryError("");
          setActivityRevision(value => value + 1);
        } while (recoverAgain);
      } catch (cause) {
        if (!cancelled) setRecoveryError(cause instanceof Error ? cause.message : "历史证据同步失败");
      } finally { recovering = false; }
    }
    const unsubscribe = subscribeToAuditStream(null, message => {
      setConnected(true);
      setActivityRevision(value => value + 1);
      if (sessionId === message.event.session_id) {
        setSession(current => current?.session_id === sessionId && !current.events.some(event => event.event_id === message.event.event_id)
          ? { ...current, events: [...current.events, { ...message.event, risk_findings: message.risk_findings ?? [] }] } : current);
      }
      if (message.run) void recover();
    }, () => setConnected(false), () => {
      setConnected(true);
      void recover();
    }, () => void recover());
    // Also retry a failed snapshot while a quiet stream stays connected.
    const timer = setInterval(() => void recover(), 30000);
    return () => { cancelled = true; clearInterval(timer); unsubscribe(); };
  }, [session?.session_id]);

  async function refreshTask(id: string) {
    if (selectedTask.current !== id) return;
    const version = navigation.current;
    try {
      const value = await getTask(id);
      if (navigation.current === version && selectedTask.current === id) {
        setTask(value);
        setTasks(current => current.map(item => item.task_id === id ? value : item));
      }
    } catch (cause) {
      if (navigation.current === version) setError(cause instanceof Error ? cause.message : "无法刷新 Task");
    }
  }

  return <main className="min-h-screen bg-zinc-50 text-zinc-950 dark:bg-black dark:text-zinc-50">
    <header className="border-b border-zinc-200 bg-white/90 px-4 py-4 dark:border-zinc-800 dark:bg-black/80">
      <div className="mx-auto flex max-w-[1600px] items-center justify-between">
        <div><h1 className="text-lg font-bold">EvolveTrace</h1><p className="text-xs text-zinc-500">看清执行记录，找到需要处理的问题</p></div>
        <span className="text-xs text-zinc-500"><i className={`mr-2 inline-block h-2 w-2 rounded-full ${connected ? "bg-emerald-500" : "bg-zinc-300"}`} />{connected ? "事件流已连接" : "事件流未连接"}</span>
      </div>
    </header>
    <div className="mx-auto grid min-h-[calc(100vh-73px)] max-w-[1600px] lg:grid-cols-[260px_minmax(400px,1fr)_minmax(300px,.8fr)]">
      <TaskList projects={projects} selectedProjectId={projectId} onSelectProject={selectProject} tasks={tasks} unboundRuns={unbound} selectedTaskId={task?.task_id ?? null} selectedSessionId={sessionId} onSelectTask={id => void selectTask(id)} onSelectUnbound={id => void selectSession(id)} />
      <section className="min-w-0 border-b border-zinc-200 p-4 dark:border-zinc-800 sm:p-6 lg:border-b-0">
        {error && <p className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950/40 dark:text-red-200">{error}</p>}
        {recoveryError && <p className="mb-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-950/40 dark:text-amber-200">历史证据同步暂未完成，将自动重试：{recoveryError}</p>}
        <ActivityPanel revision={activityRevision} selectedProjectId={projectId} sessionId={sessionId} onProjectsChanged={updateProjects} onScopeEventsChanged={updateScopeEvents} onSelectSession={id => void selectSession(id)} />
        {!task && !session && <div className="rounded-xl border border-dashed border-zinc-300 p-5 text-sm text-zinc-500 dark:border-zinc-700"><p className="font-medium text-zinc-700 dark:text-zinc-300">从一次会话开始查看证据</p><p className="mt-2">在左侧选择项目，再选择一次会话，查看命令时间线和右侧详情。想按验收条件复核任务，可展开左侧「任务验收」。</p></div>}
        {task && <details open className="mb-5 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800"><summary className="cursor-pointer text-sm font-semibold">任务验收 · {task.title}</summary>
        <TaskOverview task={task} />
        <ContextSnapshotCard task={task} />
        <ContextReceiptCard receipts={task?.context_receipts ?? []} />
        <RunList runs={task?.runs ?? []} selectedId={session?.session_id ?? null} onSelect={id => void selectSession(id, task)} />
        <EvaluationPanel task={task} sessionId={session?.session_id ?? null} onChanged={() => { if (task) void refreshTask(task.task_id); }} />
        {task && <RunWorkflow key={task.task_id} task={task} onChanged={() => void refreshTask(task.task_id)} />}
        </details>}
        {session && <div className="mt-5"><h2 className="mb-2 text-sm font-semibold">会话执行时间线 · {session.session_id.slice(0, 8)}</h2><p className="mb-3 text-xs text-zinc-500">{projectId ? "按所选项目与会话筛选，" : "所选会话中"}{scopedEvents.length} 条已入库事件；开始与结束可能属于同一次调用，因此事件数不等于调用次数。点击步骤查看右侧证据。</p><AuditTimeline steps={steps} selectedId={selectedStep?.id ?? null} onSelect={step => setSelectedStepId(step.id)} /></div>}
      </section>
      <aside className="flex min-h-0 flex-col bg-white dark:bg-zinc-950">
        <div className="min-h-0 flex-1 overflow-y-auto"><EventInspector step={selectedStep} /></div>
        <ReviewComposer event={selectedStep?.event ?? null} />
      </aside>
    </div>
  </main>;
}
