"use client";

import { useEffect, useRef, useState } from "react";
import { activateTask, compareRuns, listEvaluations } from "@/app/lib/harness-api";
import { comparisonRows, reviewedRuns } from "@/app/lib/run-comparison";
import type { EvaluationResult, Run, RunComparison, TaskContract } from "@/app/lib/harness-types";

const buttonClass = "rounded bg-teal-600 px-3 py-2 text-xs text-white disabled:opacity-40";
const fieldClass = "mt-1 w-full rounded border border-zinc-300 bg-transparent p-2 text-xs dark:border-zinc-700";
const outcomeLabels = { passed: "通过", failed: "失败", needs_review: "待复核", skipped: "跳过" };

export function RunWorkflow({ task, onChanged }: { task: TaskContract; onChanged: () => void }) {
  const [repository, setRepository] = useState("");
  const [originalId, setOriginalId] = useState("");
  const [correctedId, setCorrectedId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const active = useRef(true);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  const originals = reviewedRuns(task, "needs_fix");
  const original = originals.find(run => run.run_id === originalId) ?? originals[0];
  const corrections = reviewedRuns(task, "accepted").filter(run => run.run_id !== original?.run_id
    && !!original && run.started_at > original.started_at);
  const corrected = corrections.find(run => run.run_id === correctedId) ?? corrections[0];
  const repositoryPath = task.target_repositories.includes(repository) ? repository : task.target_repositories[0] ?? "";
  const running = (task.runs ?? []).some(run => run.status === "running");

  async function prepare() {
    if (busy || !repositoryPath || task.status !== "needs_fix" || running) return;
    setBusy(true); setError("");
    try {
      await activateTask(task.task_id, repositoryPath);
      if (active.current) onChanged();
    } catch (cause) {
      if (active.current) setError(cause instanceof Error ? cause.message : "准备修正运行失败");
    } finally { if (active.current) setBusy(false); }
  }

  if (!original && task.status !== "needs_fix") return null;
  return <section aria-label="修正与复验" className="mt-5 rounded-xl border border-zinc-200 p-4 text-sm dark:border-zinc-800">
    <h3 className="font-semibold">修正与复验</h3>
    {task.status === "needs_fix" && <div className="mt-3 space-y-3">
      <p className="text-xs text-zinc-500">沿用当前 Task 的上下文快照和验收条件，保留旧 Run 的评估与复核。所选仓库的后续新会话将绑定到此 Task。</p>
      <label className="block text-xs">修正目标仓库<select disabled={busy} className={fieldClass} value={repositoryPath} onChange={event => setRepository(event.target.value)}>
        {task.target_repositories.map(path => <option key={path} value={path}>{path}</option>)}
      </select></label>
      <button className={buttonClass} disabled={busy || running || !repositoryPath} onClick={() => void prepare()}>{busy ? "准备中…" : "准备修正运行"}</button>
      {running && <p role="status" className="text-xs text-amber-700">请先结束当前正在运行的会话。</p>}
    </div>}
    {task.status === "active" && <p role="status" className="mt-3 rounded bg-teal-50 p-3 text-xs text-teal-800 dark:bg-teal-950 dark:text-teal-200">
      当前 Task 为 active。请在所选目标仓库中新开 Codex 会话执行修正；第一条匹配 Hook 到达后才创建新 Run。原会话不会变成新 Run。
      新 Run 出现后，从 Task Runs 选择它，等待结束，再评估并人工复核。
    </p>}
    {error && <p role="alert" className="mt-2 text-xs text-red-600">{error}</p>}
    {original && <div className="mt-4 space-y-3">
      <label className="block text-xs">原始 Run（需修复）<select className={fieldClass} value={original.run_id} onChange={event => { setOriginalId(event.target.value); setCorrectedId(""); }}>
        {originals.map(run => <option key={run.run_id} value={run.run_id}>{run.session_id ?? run.run_id}</option>)}
      </select></label>
      <p className="break-words text-xs text-zinc-500">原复核：{original.review_decision!.note}</p>
      {corrected ? <>
        <label className="block text-xs">修正 Run（已接受）<select className={fieldClass} value={corrected.run_id} onChange={event => setCorrectedId(event.target.value)}>
          {corrections.map(run => <option key={run.run_id} value={run.run_id}>{run.session_id ?? run.run_id}</option>)}
        </select></label>
        <Comparison key={`${task.task_id}:${original.run_id}:${corrected.run_id}`} taskId={task.task_id} original={original} corrected={corrected}
          savedResult={task.run_comparisons?.find(item => item.task_id === task.task_id && item.original_run_id === original.run_id && item.corrected_run_id === corrected.run_id)} onChanged={onChanged} />
      </> : <p className="text-xs text-zinc-500">等待较新的 Run 完成评估并由人工接受。已有决定的 Run 保持只读。</p>}
    </div>}
  </section>;
}

function Comparison({ taskId, original, corrected, savedResult, onChanged }: { taskId: string; original: Run; corrected: Run; savedResult?: RunComparison; onChanged: () => void }) {
  const [evidence, setEvidence] = useState<{ before: EvaluationResult[]; after: EvaluationResult[] } | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [result, setResult] = useState<RunComparison | null>(null);
  const confirmed = result ?? savedResult;
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    let cancelled = false;
    void Promise.all([listEvaluations(taskId, original.run_id), listEvaluations(taskId, corrected.run_id)])
      .then(([before, after]) => { if (!cancelled) setEvidence({ before, after }); })
      .catch(cause => { if (!cancelled) setError(cause instanceof Error ? cause.message : "读取对比证据失败"); })
      .finally(() => { if (!cancelled) setBusy(false); });
    return () => { cancelled = true; active.current = false; };
  }, [taskId, original.run_id, corrected.run_id]);
  async function confirm() {
    if (busy || !evidence || confirmed) return;
    setBusy(true); setError("");
    try {
      const value = await compareRuns(taskId, original.run_id, corrected.run_id);
      if (active.current) { setResult(value); onChanged(); }
    } catch (cause) {
      if (active.current) setError(cause instanceof Error ? cause.message : "比较未完成");
    } finally { if (active.current) setBusy(false); }
  }
  return <div className="space-y-3">
    <p className="text-xs text-zinc-500">修正复核：{corrected.review_decision!.note}</p>
    {busy && <p role="status" className="text-xs text-zinc-500">正在读取或确认所选 Run 对比…</p>}
    {error && <p role="alert" className="text-xs text-red-600">{error}</p>}
    {evidence && <div className="overflow-x-auto"><table className="w-full text-left text-xs">
      <caption className="mb-2 text-left">同一验收条件的前后结果</caption>
      <thead><tr><th className="p-2">条件 / 规则</th><th className="p-2">原始 Run</th><th className="p-2">修正 Run</th></tr></thead>
      <tbody>{comparisonRows(evidence.before, evidence.after).map(row => <tr className="border-t border-zinc-200 dark:border-zinc-800" key={row.key}>
        <th className="p-2 align-top font-normal">{row.criterionId}<br /><span className="text-zinc-500">{row.before?.evaluator_id ?? row.after?.evaluator_id}</span></th>
        {[row.before, row.after].map((item, index) => <td className="max-w-52 break-words p-2 align-top" key={index}>
          {item ? <><b>{outcomeLabels[item.status]}</b> · v{item.evaluator_version}<p>{item.summary}</p><p className="mt-1 text-zinc-500">证据：{item.evidence_refs.join(", ") || "缺失"}</p></> : "缺少评估"}
        </td>)}
      </tr>)}</tbody>
    </table></div>}
    <p className="text-xs text-zinc-500">确认仅关联已复核的执行结果；后端仍检查验收条件与上下文回执，不能据此推断模型理解或因果收益。</p>
    {confirmed ? <p role="status" className="break-all rounded bg-emerald-50 p-3 text-xs text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">已确认修正复验 · Context 收益未测 · 回执 {confirmed.receipt_id}</p>
      : <button className={buttonClass} disabled={busy || !evidence} onClick={() => void confirm()}>确认前后比较</button>}
  </div>;
}
