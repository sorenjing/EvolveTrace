"use client";

import { useEffect, useRef, useState } from "react";
import { fetchActivity, fetchAuditMemory, fetchCaptureStatus, reviewActivity, revokeAuditMemory, saveAuditMemory, unmuteActivity } from "@/app/lib/activity-api";
import { activityPrompt } from "@/app/lib/activity-prompt";
import type { ActivityCategory, ActivityCode, ActivityFinding, ActivityProject, ActivityReport, ActivitySummary, AuditMemoryEntry, AuditMemoryRecall, CaptureStatus } from "@/app/lib/activity-types";

const categoryLabels: Record<ActivityCategory, string> = {
  read_search: "搜索与读取", edit: "修改", build_test: "构建与测试", dependencies: "依赖管理",
  git: "Git", network: "网络", mixed: "组合命令", other: "其他工具",
};
const ruleLabels: Record<ActivityCode, string> = { repeated_read: "重复搜索或读取", repeated_build: "重复构建或测试", failed_retry: "连续失败重试" };
const buttonClass = "rounded-lg border border-zinc-300 px-3 py-1.5 text-xs hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800";

export function ActivityPanel({ revision, selectedProjectId, sessionId, onProjectsChanged, onScopeEventsChanged, onSelectSession }: {
  revision: number; selectedProjectId: string | null; sessionId: string | null;
  onProjectsChanged: (projects: ActivityProject[]) => void; onSelectSession: (id: string) => void;
  onScopeEventsChanged: (sessionId: string, projectId: string | null, eventIds: string[]) => void;
}) {
  const [report, setReport] = useState<ActivityReport | null>(null);
  const [capture, setCapture] = useState<CaptureStatus | null>(null);
  const [captureError, setCaptureError] = useState("");
  const [scopedResult, setScopedResult] = useState<{ id: string; report: ActivityReport } | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [memoryResult, setMemoryResult] = useState<{ projectId: string; entries: AuditMemoryEntry[]; history?: AuditMemoryEntry[]; recalls?: AuditMemoryRecall[]; error: string } | null>(null);
  const [dialog, setDialog] = useState<{ project: ActivityProject; finding: ActivityFinding } | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const currentRevision = useRef(revision);
  const project = report?.projects.find(item => item.project_id === selectedProjectId);
  const activeReport = sessionId ? scopedResult?.id === sessionId ? scopedResult.report : null : report;
  const scopedProject = activeReport?.projects.find(item => item.project_id === selectedProjectId);
  const activity = selectedProjectId ? scopedProject?.activity : activeReport?.overall_activity;
  const scopeLabel = `${project ? project.name : "全部项目"}${sessionId ? ` / 会话 ${sessionId.slice(0, 8)}` : " / 全部会话"}`;
  const policy = report?.rule_policy;
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
      void Promise.all([fetchActivity(controller.signal), sessionId ? fetchActivity(controller.signal, sessionId) : Promise.resolve(null)]).then(([value, scoped]) => {
        if (controller.signal.aborted) return;
        setReport(value);
        onProjectsChanged(value.projects);
        if (sessionId && scoped?.scope?.session_id !== sessionId) throw new Error("当前后端尚不支持会话统计，请重启 EvolveTrace 服务");
        if (sessionId && scoped) {
          setScopedResult({ id: sessionId, report: scoped });
          const eventIds = scoped.projects.find(item => item.project_id === selectedProjectId)?.event_ids ?? [];
          onScopeEventsChanged(sessionId, selectedProjectId, eventIds);
        }
        setError("");
      }).catch(cause => {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "无法读取项目审计");
      }).finally(() => { inFlight = false; });
    }
    load();
    const timer = window.setInterval(load, 1000);
    return () => { window.clearInterval(timer); controller.abort(); };
  }, [refresh, sessionId, selectedProjectId, onProjectsChanged, onScopeEventsChanged]);

  useEffect(() => {
    if (!memoryProjectId) return;
    const projectId = memoryProjectId;
    const controller = new AbortController();
    let inFlight = false;
    function load() {
      if (inFlight) return;
      inFlight = true;
      void fetchAuditMemory(projectId, controller.signal).then(value => {
        if (!controller.signal.aborted) setMemoryResult({ projectId, entries: value.entries, history: value.history, recalls: value.recalls, error: "" });
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

  async function revoke(entry: AuditMemoryEntry) {
    if (!project || busy) return;
    setBusy(true);
    try { await revokeAuditMemory(project.project_id, entry.memory_id); setRefresh(value => value + 1); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "撤销失败"); }
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
    <div className="flex items-center justify-between gap-2"><div><p className="text-[10px] font-semibold uppercase tracking-widest text-teal-600">执行观察</p><h2 className="mt-1 text-lg font-semibold">命令统计与行为提醒</h2></div><button type="button" className={buttonClass} onClick={() => setRefresh(value => value + 1)}>刷新</button></div>
    <ol className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-zinc-500"><li>1. 选择左侧项目或会话</li><li>2. 核对提醒与命令证据</li><li>3. 需要时分析并记录结论</li></ol>
    <div className="mt-4 rounded-lg border border-teal-200 bg-teal-50 p-3 dark:border-teal-900 dark:bg-teal-950/30">
      <p className="text-xs font-medium text-teal-800 dark:text-teal-200">当前统计范围</p><p className="mt-1 break-words text-sm font-semibold">{scopeLabel}</p>
      <p className="mt-1 text-xs text-zinc-500">{sessionId ? "仅统计所选会话在此范围内的操作。" : "选择会话后，统计与下方时间线会同步切换。"}数据来自最近入库的有界记录，不是「今天」或全量历史。</p>
    </div>
    <details className="mt-3 rounded-lg bg-zinc-50 p-3 text-xs dark:bg-zinc-900">
      <summary className="cursor-pointer font-medium">采集状态 · {captureError ? "暂不可用" : !capture ? "读取中" : capture.capture_state === "receiving" ? "最近 60 秒收到事件" : capture.capture_state === "quiet" ? "最近 60 秒无新事件，可能空闲" : "等待新事件"}</summary>
      {captureError && <p className="mt-2 text-amber-700 dark:text-amber-300">{captureError}{capture ? " 下列为上次成功读取的数据。" : ""}</p>}
      {capture && <><p className="mt-2">本次启动收到 {capture.received_event_count} 条事件 · 去重后新增 {capture.persisted_event_count} 条 · 历史存储 {capture.stored_event_count} 条 · 已登记 {capture.registered_project_count} 个项目</p>
        <p className="mt-1 text-zinc-500">这是全局采集状态，不随项目筛选。收件数可包含重复上报；不等于命令执行次数。</p>
        <p className="mt-1 text-zinc-500">最后收件：{capture.last_received_at ? new Date(capture.last_received_at).toLocaleString("zh-CN") : "暂无"} · 每 15 秒更新</p>
        {capture.evidence_worker && <p className="mt-1 text-zinc-500">后台补齐：{capture.evidence_worker.state} · 本轮尝试 {capture.evidence_worker.attempted} 条 · 补齐 {capture.evidence_worker.resolved} 条 · 待补齐 {capture.evidence_worker.pending ?? "尚未统计"} 条</p>}
        <p className="mt-1 break-words text-zinc-500">观察到的阶段：{capture.observed_phases.join("、") || "暂无"}。没有新事件可能是空闲，收件正常也不保证采集完整。</p></>}
    </details>
    {error && <p role="alert" className="mt-2 text-xs text-red-700 dark:text-red-300">{error}</p>}
    {!activity && !error && <p role="status" className="mt-4 text-sm text-zinc-500">正在读取此范围的统计…</p>}
    {activity && <div className="mt-4">
      <dl className="grid grid-cols-3 gap-2 sm:grid-cols-6">{[
        ["调用次数", activity.attempt_count], ["成功", activity.success_count], ["失败", activity.failed_count],
        ["取消", activity.cancelled_count], ["仅捕获开始", activity.pending_count], ["结果未知", activity.unknown_outcome_count],
      ].map(([label, value]) => <div key={label} className="rounded-lg bg-zinc-50 p-2 dark:bg-zinc-900"><dt className="text-[11px] text-zinc-500">{label}</dt><dd className="mt-1 text-lg font-semibold">{value}</dd></div>)}</dl>
      <p className="mt-2 text-xs text-zinc-500">开始与结束事件尽量合并为一次调用；「未知」和「仅捕获开始」不算失败。阻断记录 {activity.denied_count} 条。</p>
      <h3 className="mt-4 text-xs font-medium">按操作类型分类</h3>
      <dl className="mt-2 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">{Object.entries(categoryLabels).map(([key, label]) => <div key={key} className="rounded-lg border border-zinc-100 p-2 dark:border-zinc-800"><dt className="text-zinc-500">{label}</dt><dd className="mt-1 font-semibold">{activity.categories[key as ActivityCategory]}</dd></div>)}</dl>
      <ExecutionCoverage activity={activity} /><PairingNotice activity={activity} />
      <details className="mt-3 text-xs text-zinc-500"><summary className="cursor-pointer">这些数字怎么算？</summary><p className="mt-2 leading-5">一次工具调用通常产生开始、结束两条事件，配对后计为一次调用。搜索与读取如 rg、Get-Content；修改如 apply_patch、文件写入；构建与测试含 lint、类型检查；依赖管理如 npm install；Git 和网络请求分别记录。带管道、分号或多个命令的脚本保守归为「组合命令」，不会虚构子命令次数。</p><p className="mt-2 leading-5">耗时只累计拿到明确耗时的样本；并行命令耗时相加不等于会话墙钟时间。命令次数不能换算成磁盘读写量、CPU 消耗或硬件健康。</p></details>
    </div>}
    <details className="mt-4 rounded-lg border border-zinc-200 p-3 text-xs dark:border-zinc-800"><summary className="cursor-pointer font-medium">提醒规则与阈值 · 经验默认值</summary>
      {policy ? <ul className="mt-2 list-inside list-disc space-y-2 text-zinc-500"><li>每个会话以最后一次已观察操作为终点，检查前 {policy.window_seconds / 60} 分钟；历史提醒不表示当前仍在异常。</li><li>同命令、同目录搜索读取或构建测试至少 {policy.repeated_operation_min} 次，且期间未捕获修改，提示核对重复操作。</li><li>同命令、同目录连续观察失败至少 {policy.failed_retry_min} 次，提示核对重试；成功或未知结果打断失败序列。</li><li>规则版本 {policy.version}。这些是启发式提醒，尚未按真实任务标定，不是行业标准，不自动阻断命令；正常验证也可能命中。</li></ul> : <p className="mt-2 text-zinc-500">当前后端未返回规则参数，请重启更新后的服务以查看阈值依据。</p>}
    </details>
    {report && !report.projects.length && <p className="mt-3 text-sm text-zinc-500">尚未连接项目目录。通过 Context 登记工作区后，已有执行记录也可归入对应项目。</p>}
    {report && !project && <p className="mt-4 rounded-lg bg-zinc-50 p-3 text-xs leading-5 text-zinc-500 dark:bg-zinc-900">选择左侧项目可处理该项目的行为提醒与人工确认记忆。未归属会话也能独立查看统计和证据。</p>}
    {report && project && <>
      <h3 className="mt-5 text-sm font-semibold">需要核对的行为 · {sessionId ? "当前会话" : project.name}</h3>
      {(scopedProject?.activity.findings ?? []).filter(item => !item.suppressed).map(finding => <div key={finding.finding_id} className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-900 dark:bg-amber-950/20">
        <p className="text-sm font-medium">{ruleLabels[finding.code]}</p><p className="mt-1 text-xs">该会话最后一次已观察操作前 {finding.window_seconds / 60} 分钟内，共 {finding.count} 次。{finding.code === "failed_retry" ? "同命令、同目录连续失败；建议检查错误原因后再重试。" : "同命令、同目录重复操作，期间未捕获修改；建议核对是否必要。"}这是一条待核对线索。</p>
        <div className="mt-2 flex flex-wrap gap-2"><button type="button" className={buttonClass} onClick={() => setDialog({ project, finding })}>选择分析</button><button type="button" className={buttonClass} onClick={() => onSelectSession(finding.session_id)}>查看证据</button><button type="button" disabled={busy} className={buttonClass} onClick={() => void decide(finding, "ignore")}>忽略本次</button><button type="button" disabled={busy} className={buttonClass} onClick={() => void decide(finding, "mute")}>静音此类</button></div>
      </div>)}
      {activity && !(scopedProject?.activity.findings ?? []).some(item => !item.suppressed) && <p className="mt-3 text-xs text-zinc-500">当前采集范围内暂无待提醒的行为线索。</p>}
      {project.activity.muted_rules.map(code => <button type="button" key={code} disabled={busy} className={`${buttonClass} mr-2 mt-2`} onClick={() => void unmute(code)}>恢复：{ruleLabels[code]}</button>)}
      <details className="mt-4"><summary className="cursor-pointer text-xs font-medium">可复用结论 · 项目记忆</summary><section aria-label="项目审计记忆" className="mt-4 border-t border-zinc-200 pt-3 text-xs dark:border-zinc-800">
        <h3 className="font-medium">已确认的审计记忆 · {project.name}{memory && !memory.error ? `（${memory.entries.length}）` : ""}</h3>
        <p className="mt-1 text-zinc-500">本项目的人工确认结论，可供后续会话回读；不会自动套用其他项目的经验，也不代表模型已经采用。</p>
        {!memory && <p role="status" className="mt-2 text-zinc-500">正在读取本项目记忆…</p>}
        {memory?.error && <p role="alert" className="mt-2 text-amber-700 dark:text-amber-300">{memory.error}。请刷新重试；读取失败不代表没有记忆。</p>}
        {memory && !memory.error && !memory.entries.length && <p className="mt-2 rounded-lg bg-zinc-50 p-3 dark:bg-zinc-900">当前没有仍可回读的人工确认记忆。出现执行线索后，可选择分析、核对证据并保存适用结论；采集命令不会自动生成记忆。项目目标和约束另由 Context 的 manual 区维护。</p>}
        {memory && !memory.error && <MemoryRecallHistory entries={memory.entries} recalls={memory.recalls} />}
        {memory && !memory.error && memory.entries.map(entry => <article id={`audit-memory-${entry.memory_id}`} key={entry.memory_id} className="mt-2 rounded-lg bg-zinc-50 p-3 dark:bg-zinc-900">
          <p className="whitespace-pre-wrap break-words">{entry.note}</p>
          <p className="mt-2 text-zinc-500">人工确认 · 历史观察 · {entry.created_at.slice(0, 10)} · {entry.evidence_refs.length} 条证据</p>
          {entry.applicability && <p className="mt-1 text-zinc-500">适用条件：{entry.applicability}</p>}
          {entry.expires_at && <p className="mt-1 text-zinc-500">到期时间：{new Date(entry.expires_at).toLocaleString()}</p>}
          <button type="button" className={`${buttonClass} mt-2`} onClick={() => onSelectSession(entry.session_id)}>查看来源会话</button>
          <button type="button" disabled={busy} className={`${buttonClass} ml-2 mt-2`} onClick={() => void revoke(entry)}>撤销记忆</button>
          <details className="mt-2 break-all text-zinc-500"><summary className="cursor-pointer">记忆与证据标识</summary><p className="mt-1">{entry.memory_id}</p><p>{entry.evidence_refs.join("、")}</p></details>
        </article>)}
        {!!memory?.history?.length && <details className="mt-3 text-zinc-500"><summary className="cursor-pointer">已停止回读的记忆（最近 20 条）</summary>
          {memory.history.map(entry => <article key={entry.memory_id} className="mt-2 rounded border p-2">
            <p>{{ human_reviewed: "人工确认", revoked: "已撤销", superseded: "已被替代", expired: "已过期" }[entry.status]} · {entry.note}</p>
            <button type="button" className={`${buttonClass} mt-2`} onClick={() => onSelectSession(entry.session_id)}>查看来源会话</button>
          </article>)}
        </details>}
        <details className="mt-3 text-zinc-500"><summary className="cursor-pointer">后续会话如何回读</summary><p className="mt-2">在配置的工作区运行：</p><code className="mt-1 block break-words">aictx load &lt;项目名&gt; --audit-url &lt;本地服务地址&gt;</code><p className="mt-2">也可在启动 Codex 的环境中设置 EVOLVETRACE_AUDIT_MEMORY_URL，由 SessionStart 和后续 load 沿用。默认保持离线；启动服务或看到这张卡片不等于已启用回读。</p></details>
      </section></details>
    </>}
    {activeReport && <details className="mt-4 text-xs text-zinc-500"><summary className="cursor-pointer">采集覆盖与归属依据</summary><p className="mt-2">先取最近入库的至多 {activeReport.event_limit.toLocaleString()} 条事件，再应用会话和项目筛选。{sessionId ? "所选会话" : "当前读取范围"}返回 {activeReport.observed_event_count} 条事件，其中 {activeReport.unattributed_event_count} 条未归属项目；项目卡片仅统计可确认归属的操作。</p><p className="mt-1">归属依据：Hook 目录 {activeReport.attribution_sources.hook_cwd} 条 · 工具工作目录 {activeReport.attribution_sources.tool_workdir} 条 · 已核对执行记录 {activeReport.attribution_sources.execution_record} 条。</p>{activeReport.truncated && <p className="mt-1 text-amber-700 dark:text-amber-300">已达到全局采集分析上限，较早记录未计入；空结果不代表没有历史记录。</p>}{activeReport.execution_metadata_scan.limited && <p className="mt-1">执行记录读取已受范围限制，较早记录可能无法补全。</p>}</details>}
    {dialog && <AnalysisDialog key={dialog.finding.finding_id} {...dialog} memories={dialog.project.project_id === memoryProjectId ? memory?.entries ?? [] : []} onClose={() => setDialog(null)} onSaved={() => setRefresh(value => value + 1)} />}
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

function AnalysisDialog({ project, finding, memories, onClose, onSaved }: { project: ActivityProject; finding: ActivityFinding; memories: AuditMemoryEntry[]; onClose: () => void; onSaved: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [note, setNote] = useState("");
  const [applicability, setApplicability] = useState("");
  const [expiry, setExpiry] = useState("");
  const [supersedes, setSupersedes] = useState("");
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
    try { await saveAuditMemory(project.project_id, finding, note.trim(), {
      applicability: applicability.trim(), ...(expiry ? { expires_at: new Date(expiry).toISOString() } : {}),
      ...(supersedes ? { supersedes } : {}),
    }); setMessage("已保存为本项目的人工确认记忆。"); setNote(""); setSupersedes(""); setConfirmed(false); onSaved(); }
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
    <label className="mt-2 block text-xs">适用条件（可选）<input maxLength={300} value={applicability} onChange={event => setApplicability(event.target.value)} className="mt-1 block w-full rounded border bg-transparent p-2" /></label>
    <label className="mt-2 block text-xs">到期时间（可选，本地时间）<input type="datetime-local" value={expiry} onChange={event => setExpiry(event.target.value)} className="mt-1 block rounded border bg-transparent p-2" /></label>
    {!!memories.length && <label className="mt-2 block text-xs">替代旧结论（可选）<select value={supersedes} onChange={event => setSupersedes(event.target.value)} className="mt-1 block w-full rounded border bg-transparent p-2">
      <option value="">保存为独立记忆</option>{memories.map(entry => <option key={entry.memory_id} value={entry.memory_id}>{entry.note.slice(0, 60)}</option>)}
    </select></label>}
    <label className="mt-2 flex items-center gap-2 text-xs"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />我已核对相关证据并确认这条结论</label>
    <button type="button" disabled={busy || !confirmed || !note.trim()} className={`${buttonClass} mt-3`} onClick={() => void save()}>保存审计记忆</button>
    <p aria-live="polite" className="mt-2 text-xs">{message}</p>
  </dialog>;
}
