"use client";

import { useEffect, useRef, useState } from "react";
import { fetchActivity, fetchAuditMemory, fetchCaptureStatus, reviewActivity, saveAuditMemory, unmuteActivity } from "@/app/lib/activity-api";
import { activityPrompt } from "@/app/lib/activity-prompt";
import type { ActivityCategory, ActivityCode, ActivityFinding, ActivityProject, ActivityReport, ActivitySummary, AuditMemoryEntry, AuditMemoryRecall, CaptureStatus } from "@/app/lib/activity-types";

const categoryLabels: Record<ActivityCategory, string> = {
  read_search: "搜索与读取", edit: "修改", build_test: "构建与测试", dependencies: "依赖管理",
  git: "Git", network: "网络", mixed: "组合命令", other: "其他工具",
};
const ruleLabels: Record<ActivityCode, string> = { repeated_read: "重复搜索或读取", repeated_build: "重复构建或测试", failed_retry: "连续失败重试" };
const buttonClass = "rounded-lg border border-zinc-300 px-3 py-1.5 text-xs hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800";

export function ActivityPanel({ revision, onSelectSession }: { revision: number; onSelectSession: (id: string) => void }) {
  const [report, setReport] = useState<ActivityReport | null>(null);
  const [capture, setCapture] = useState<CaptureStatus | null>(null);
  const [captureError, setCaptureError] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [memoryResult, setMemoryResult] = useState<{ projectId: string; entries: AuditMemoryEntry[]; recalls?: AuditMemoryRecall[]; error: string } | null>(null);
  const [dialog, setDialog] = useState<{ project: ActivityProject; finding: ActivityFinding } | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const currentRevision = useRef(revision);
  const project = report?.projects.find(item => item.project_id === selectedId) ?? report?.projects[0];
  const memoryProjectId = project?.project_id;
  const memory = memoryResult?.projectId === memoryProjectId ? memoryResult : null;

  useEffect(() => { currentRevision.current = revision; }, [revision]);

  useEffect(() => {
    const controller = new AbortController();
    let inFlight = false;
    function load() {
      if (inFlight) return;
      inFlight = true;
      void fetchCaptureStatus(controller.signal).then(value => {
        if (!controller.signal.aborted) { setCapture(value); setCaptureError(""); }
      }).catch(() => {
        if (!controller.signal.aborted) setCaptureError("采集状态暂不可用，请检查本地服务。");
      }).finally(() => { inFlight = false; });
    }
    load();
    const timer = window.setInterval(load, 15000);
    return () => { window.clearInterval(timer); controller.abort(); };
  }, [refresh]);

  useEffect(() => {
    const controller = new AbortController();
    let lastRequested = -1;
    let lastRequestAt = 0;
    let inFlight = false;
    function load() {
      if (inFlight || (lastRequested === currentRevision.current && Date.now() - lastRequestAt < 15000)) return;
      lastRequested = currentRevision.current;
      lastRequestAt = Date.now();
      inFlight = true;
      void fetchActivity(controller.signal).then(value => { if (!controller.signal.aborted) { setReport(value); setError(""); } }).catch(cause => {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "无法读取项目审计");
      }).finally(() => { inFlight = false; });
    }
    load();
    const timer = window.setInterval(load, 1000);
    return () => { window.clearInterval(timer); controller.abort(); };
  }, [refresh]);

  useEffect(() => {
    if (!memoryProjectId) return;
    const projectId = memoryProjectId;
    const controller = new AbortController();
    let inFlight = false;
    function load() {
      if (inFlight) return;
      inFlight = true;
      void fetchAuditMemory(projectId, controller.signal).then(value => {
        if (!controller.signal.aborted) setMemoryResult({ projectId, entries: value.entries, recalls: value.recalls, error: "" });
      }).catch(cause => {
        if (!controller.signal.aborted) setMemoryResult({ projectId, entries: [], error: cause instanceof Error ? cause.message : "无法读取审计记忆" });
      }).finally(() => { inFlight = false; });
    }
    load();
    const timer = window.setInterval(load, 15000);
    return () => { window.clearInterval(timer); controller.abort(); };
  }, [memoryProjectId, refresh]);

  async function decide(finding: ActivityFinding, action: "ignore" | "mute") {
    if (!project) return;
    setBusy(true);
    try { await reviewActivity(project.project_id, finding, action); setRefresh(value => value + 1); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "无法保存提醒设置"); }
    finally { setBusy(false); }
  }

  async function unmute(code: ActivityCode) {
    if (!project) return;
    setBusy(true);
    try { await unmuteActivity(project.project_id, code); setRefresh(value => value + 1); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "无法恢复提醒"); }
    finally { setBusy(false); }
  }

  return <section aria-label="跨项目执行审计" className="mb-5 rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
    <div className="flex items-center justify-between gap-2"><h2 className="text-sm font-semibold">跨项目执行审计</h2><button type="button" className={buttonClass} onClick={() => setRefresh(value => value + 1)}>刷新</button></div>
    <p className="mt-2 text-xs text-zinc-500">按项目观察命令与重试；需要时选择分析，再确认可复用的结论。</p>
    <div aria-live="polite" className="mt-3 rounded-lg bg-zinc-50 p-3 text-xs dark:bg-zinc-900">
      {captureError ? <p className="text-amber-700 dark:text-amber-300">{captureError}{capture ? " 下列为上次成功读取的数据。" : ""}</p> : <p className="font-medium">{!capture ? "正在读取采集状态…" : capture.capture_state === "receiving" ? "最近 60 秒收到 Hook 事件" : capture.capture_state === "quiet" ? "最近 60 秒未收到事件，可能处于空闲" : "服务已连接，本次启动后尚未收到 Hook 事件"}</p>}
      {capture && <><p className="mt-1">本次启动收到 {capture.received_event_count} 条 · 新增存储 {capture.persisted_event_count} 条 · 历史存储 {capture.stored_event_count} 条 · 已登记 {capture.registered_project_count} 个项目</p>
        <p className="mt-1 text-zinc-500">最后收件：{capture.last_received_at ? new Date(capture.last_received_at).toLocaleString("zh-CN") : "暂无"} · 每 15 秒更新</p>
        {capture.evidence_worker && <p className="mt-1 text-zinc-500">后台证据补齐：{capture.evidence_worker.state === "running" ? "运行中" : capture.evidence_worker.state === "error" ? "本轮出错，将重试" : "已停止"} · 上轮尝试 {capture.evidence_worker.attempted} 条 · 补齐 {capture.evidence_worker.resolved} 条 · 待补齐 {capture.evidence_worker.pending ?? "尚未统计"} 条</p>}
        <p className="mt-1 break-words text-zinc-500">本次观察到的阶段：{capture.observed_phases.join("、") || "暂无"}。收件状态不代表采集完整；空闲不代表 Hook 已断开。</p></>}
    </div>
    {error && <p role="alert" className="mt-2 text-xs text-red-700 dark:text-red-300">{error}</p>}
    {report && <div className="mt-3 border-b border-zinc-200 pb-3 dark:border-zinc-800">
      <h3 className="text-xs font-medium">全部已采集命令（含未归属目录）</h3>
      <p className="mt-2 text-sm">{report.overall_activity.attempt_count} 次调用观察 · 成功 {report.overall_activity.success_count} · 失败 {report.overall_activity.failed_count} · 取消 {report.overall_activity.cancelled_count}</p>
      <ExecutionCoverage activity={report.overall_activity} />
      <dl className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">{Object.entries(categoryLabels).map(([key, label]) => <div key={key} className="rounded-lg bg-zinc-50 p-2 dark:bg-zinc-900"><dt className="text-zinc-500">{label}</dt><dd className="mt-1 font-semibold">{report.overall_activity.categories[key as ActivityCategory]}</dd></div>)}</dl>
      <PairingNotice activity={report.overall_activity} />
      <p className="mt-2 text-xs text-zinc-500">已归属事件的依据：Hook 目录 {report.attribution_sources.hook_cwd} 条 · 工具工作目录 {report.attribution_sources.tool_workdir} 条 · 已核对执行记录 {report.attribution_sources.execution_record} 条</p>
      {report.unattributed_event_count > 0 && <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">{report.unattributed_event_count} 条事件仍未归属项目，已计入总览；缺少可核对的执行目录时保持未知。</p>}
      {report.execution_metadata_scan.limited && <p className="mt-1 text-xs text-zinc-500">执行记录读取已受范围限制，较早记录可能无法补全。已核对的目录回执会保留。</p>}
    </div>}
    {report && !report.projects.length && <p className="mt-3 text-sm text-zinc-500">尚未连接项目目录。通过 Context 登记工作区后，已有执行记录也可归入对应项目。</p>}
    {report && project && <>
      <label className="mt-3 block text-xs">项目<select aria-label="审计项目" value={project.project_id} onChange={event => setSelectedId(event.target.value)} className="ml-2 max-w-full rounded-lg border border-zinc-300 bg-transparent p-2 dark:border-zinc-700">
        {report.projects.map(item => <option key={item.project_id} value={item.project_id}>{item.name} · {item.relative_path}{item.active ? "" : "（历史项目）"}</option>)}
      </select></label>
      <p className="mt-3 text-sm">{project.activity.attempt_count} 次调用观察 · {project.session_count} 个会话 · {project.activity.failed_count} 次已观察失败 · {project.activity.denied_count} 次阻断</p>
      <dl className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">{Object.entries(categoryLabels).map(([key, label]) => <div key={key} className="rounded-lg bg-zinc-50 p-2 dark:bg-zinc-900"><dt className="text-zinc-500">{label}</dt><dd className="mt-1 font-semibold">{project.activity.categories[key as ActivityCategory]}</dd></div>)}</dl>
      <ExecutionCoverage activity={project.activity} />
      <PairingNotice activity={project.activity} />
      {project.activity.findings.filter(item => !item.suppressed).map(finding => <div key={finding.finding_id} className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-900 dark:bg-amber-950/20">
        <p className="text-sm font-medium">{ruleLabels[finding.code]}</p><p className="mt-1 text-xs">会话采集窗口 {finding.window_seconds / 60} 分钟内，观察到 {finding.count} 次相关操作，需核对是否必要。</p>
        <div className="mt-2 flex flex-wrap gap-2"><button type="button" className={buttonClass} onClick={() => setDialog({ project, finding })}>选择分析</button><button type="button" className={buttonClass} onClick={() => onSelectSession(finding.session_id)}>查看证据</button><button type="button" disabled={busy} className={buttonClass} onClick={() => void decide(finding, "ignore")}>忽略本次</button><button type="button" disabled={busy} className={buttonClass} onClick={() => void decide(finding, "mute")}>静音此类</button></div>
      </div>)}
      {!project.activity.findings.some(item => !item.suppressed) && <p className="mt-3 text-xs text-zinc-500">当前采集范围内暂无待提醒的行为线索。</p>}
      {project.activity.muted_rules.map(code => <button type="button" key={code} disabled={busy} className={`${buttonClass} mr-2 mt-2`} onClick={() => void unmute(code)}>恢复：{ruleLabels[code]}</button>)}
      <section aria-label="项目审计记忆" className="mt-4 border-t border-zinc-200 pt-3 text-xs dark:border-zinc-800">
        <h3 className="font-medium">已确认的审计记忆 · {project.name}{memory && !memory.error ? `（${memory.entries.length}）` : ""}</h3>
        <p className="mt-1 text-zinc-500">本项目的人工确认结论，可供后续会话回读；不会自动套用其他项目的经验，也不代表模型已经采用。</p>
        {!memory && <p role="status" className="mt-2 text-zinc-500">正在读取本项目记忆…</p>}
        {memory?.error && <p role="alert" className="mt-2 text-amber-700 dark:text-amber-300">{memory.error}。请刷新重试；读取失败不代表没有记忆。</p>}
        {memory && !memory.error && !memory.entries.length && <p className="mt-2 rounded-lg bg-zinc-50 p-3 dark:bg-zinc-900">尚未保存人工确认的审计记忆。出现执行线索后，可选择分析、核对证据并保存适用结论；采集命令不会自动生成记忆。项目目标和约束另由 Context 的 manual 区维护。</p>}
        {memory && !memory.error && <MemoryRecallHistory entries={memory.entries} recalls={memory.recalls} />}
        {memory && !memory.error && memory.entries.map(entry => <article id={`audit-memory-${entry.memory_id}`} key={entry.memory_id} className="mt-2 rounded-lg bg-zinc-50 p-3 dark:bg-zinc-900">
          <p className="whitespace-pre-wrap break-words">{entry.note}</p>
          <p className="mt-2 text-zinc-500">人工确认 · 历史观察 · {entry.created_at.slice(0, 10)} · {entry.evidence_refs.length} 条证据</p>
          <button type="button" className={`${buttonClass} mt-2`} onClick={() => onSelectSession(entry.session_id)}>查看来源会话</button>
          <details className="mt-2 break-all text-zinc-500"><summary className="cursor-pointer">记忆与证据标识</summary><p className="mt-1">{entry.memory_id}</p><p>{entry.evidence_refs.join("、")}</p></details>
        </article>)}
        <details className="mt-3 text-zinc-500"><summary className="cursor-pointer">后续会话如何回读</summary><p className="mt-2">在配置的工作区运行：</p><code className="mt-1 block break-words">aictx load &lt;项目名&gt; --audit-url &lt;本地服务地址&gt;</code><p className="mt-2">也可在启动 Codex 的环境中设置 EVOLVETRACE_AUDIT_MEMORY_URL，由 SessionStart 和后续 load 沿用。默认保持离线；启动服务或看到这张卡片不等于已启用回读。</p></details>
      </section>
    </>}
    {report && <p className="mt-3 text-xs text-zinc-500">统计覆盖最近采集的 {report.observed_event_count} 条事件；{report.unattributed_event_count} 条未归属。仅捕获开始可能是执行中或缺失结束事件。{report.truncated ? "已达到采集分析上限，较早记录未计入。" : ""}未采集系统 I/O 或硬件健康指标。</p>}
    {dialog && <AnalysisDialog key={dialog.finding.finding_id} {...dialog} onClose={() => setDialog(null)} onSaved={() => setRefresh(value => value + 1)} />}
  </section>;
}

function MemoryRecallHistory({ entries, recalls }: { entries: AuditMemoryEntry[]; recalls?: AuditMemoryRecall[] }) {
  return <section aria-label="记忆加载记录" className="mt-3 rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
    <h4 className="font-medium">最近记忆加载记录</h4>
    <p className="mt-1 text-zinc-500">客户端声明已向本地输出返回记忆；不证明宿主收到、模型理解或采用。每 15 秒刷新。</p>
    {recalls === undefined ? <p className="mt-2 text-amber-700 dark:text-amber-300">当前服务尚未提供加载记录，请更新后端。</p>
      : !recalls.length ? <p className="mt-2 text-zinc-500">暂无已上报记录。可能尚未启用回读、尚未加载或上报未成功，不能据此认定没有加载。</p>
      : recalls.slice(0, 5).map((item, index) => <details key={item.recall_id} open={index === 0} className="mt-2 border-t border-zinc-200 pt-2 dark:border-zinc-800">
        <summary className="cursor-pointer">服务收到：{new Date(item.received_at).toLocaleString("zh-CN")} · {item.trigger === "manual" ? "手动加载 / 切换项目" : item.trigger} · 返回 {item.memory_ids.length} 条</summary>
        <p className="mt-2 text-zinc-500">客户端输出时间：{new Date(item.reported_at).toLocaleString("zh-CN")} · 上下文 {item.context_status} / {item.context_freshness}</p>
        {item.truncated && <p className="mt-1 text-amber-700 dark:text-amber-300">交付预算不足，仅列出实际返回的记忆。</p>}
        {!item.memory_ids.length && <p className="mt-1 text-zinc-500">本次回读已启用，未返回记忆正文。</p>}
        <ul className="mt-1 space-y-1">{item.memory_ids.map(id => {
          const entry = entries.find(value => value.memory_id === id);
          return <li key={id} className="break-words">{entry ? <a className="text-teal-700 underline dark:text-teal-300" href={`#audit-memory-${id}`}>{entry.note.slice(0, 80)}{entry.note.length > 80 ? "…" : ""}</a> : <span className="text-zinc-500">{id}（不在当前记忆列表中）</span>}<code className="block break-all text-[10px] text-zinc-500">{id}</code></li>;
        })}</ul>
      </details>)}
    {!!recalls?.length && <p className="mt-2 text-zinc-500">展示最近 5 次，服务按项目最多保留 20 次元数据记录。普通界面查询不计入加载。</p>}
  </section>;
}

function ExecutionCoverage({ activity }: { activity: ActivitySummary }) {
  return <div className="mt-2 text-xs text-zinc-500">
    <p>结果已知 {activity.result_sample_count}/{activity.attempt_count} · 仅捕获开始 {activity.pending_count} · 结果未知 {activity.unknown_outcome_count}</p>
    <p className="mt-1">耗时覆盖 {activity.duration_sample_count}/{activity.attempt_count} 次，共 {(activity.reported_duration_ms / 1000).toFixed(1)} 秒；缺失样本未按零计算。</p>
    <p className="mt-1">结果来源：Hook {activity.result_sources.hook} · 执行记录 {activity.result_sources.execution_record} · 来源冲突 {activity.result_sources.conflict}</p>
  </div>;
}

function PairingNotice({ activity }: { activity: ActivitySummary }) {
  if (!activity.unpaired_event_count && !activity.orphan_completion_count) return null;
  return <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">配对缺口：{activity.unpaired_event_count} 条缺少调用标识，{activity.orphan_completion_count} 次结束观察缺少开始事件。次数仅反映当前采集范围。</p>;
}

function AnalysisDialog({ project, finding, onClose, onSaved }: { project: ActivityProject; finding: ActivityFinding; onClose: () => void; onSaved: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [note, setNote] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const prompt = activityPrompt(project, finding);
  useEffect(() => { const dialog = ref.current; dialog?.showModal(); return () => dialog?.close(); }, []);

  async function copy() {
    try { await navigator.clipboard.writeText(prompt); setMessage("已复制；发送到 Codex 后可进行分析。"); }
    catch { setMessage("无法访问剪贴板，请手动复制上方文本。"); }
  }
  async function save() {
    if (!confirmed || !note.trim() || busy) return;
    setBusy(true);
    try { await saveAuditMemory(project.project_id, finding, note.trim()); setMessage("已保存为本项目的人工确认记忆。"); setNote(""); setConfirmed(false); onSaved(); }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : "保存失败"); }
    finally { setBusy(false); }
  }
  return <dialog ref={ref} aria-labelledby="activity-analysis-title" onCancel={onClose} className="m-auto w-[min(640px,calc(100%-32px))] max-h-[85vh] overflow-y-auto rounded-xl bg-white p-5 text-zinc-950 shadow-xl backdrop:bg-black/40 dark:bg-zinc-950 dark:text-zinc-50">
    <div className="flex items-center justify-between"><h3 id="activity-analysis-title" className="font-semibold">分析执行线索 · {project.name}</h3><button type="button" className={buttonClass} onClick={onClose}>关闭</button></div>
    <p className="mt-3 text-sm text-zinc-500">选择是否将以下证据发送给 Codex 分析。采集记录可能不完整，请先查看相关步骤。</p>
    <textarea aria-label="Codex 分析提示" readOnly value={prompt} rows={10} className="mt-3 w-full rounded-lg border border-zinc-300 bg-transparent p-3 text-xs dark:border-zinc-700" />
    <button type="button" className={buttonClass} onClick={() => void copy()}>复制给 Codex 分析</button>
    <label className="mt-5 block text-sm font-medium" htmlFor="activity-memory-note">核对后的可复用结论</label>
    <textarea id="activity-memory-note" maxLength={1000} value={note} onChange={event => setNote(event.target.value)} rows={3} placeholder="记录适用条件和改进方法；未核实的推测请勿保存。" className="mt-2 w-full rounded-lg border border-zinc-300 bg-transparent p-3 text-sm dark:border-zinc-700" />
    <label className="mt-2 flex items-center gap-2 text-xs"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />我已核对相关证据并确认这条结论</label>
    <button type="button" disabled={busy || !confirmed || !note.trim()} className={`${buttonClass} mt-3`} onClick={() => void save()}>保存审计记忆</button>
    <p aria-live="polite" className="mt-2 text-xs">{message}</p>
  </dialog>;
}
