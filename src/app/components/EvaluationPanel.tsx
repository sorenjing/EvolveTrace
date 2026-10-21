"use client";

import { useEffect, useRef, useState } from "react";
import { evaluateRun, listEvaluations, recordReview } from "@/app/lib/harness-api";
import { reviewRun } from "@/app/lib/review-selection";
import type { EvaluationResult, ReviewDecision, TaskContract } from "@/app/lib/harness-types";

export function EvaluationPanel({ task, sessionId, onChanged }: { task: TaskContract | null; sessionId: string | null; onChanged: () => void }) {
  const run = reviewRun(task, sessionId);
  if (!task || !run) return null;
  return <RunEvaluation key={`${task.task_id}:${run.run_id}`} taskId={task.task_id} runId={run.run_id} sessionId={sessionId!} decision={run.review_decision ?? null} onChanged={onChanged} />;
}

function RunEvaluation({ taskId, runId, sessionId, decision, onChanged }: { taskId: string; runId: string; sessionId: string; decision: ReviewDecision | null; onChanged: () => void }) {
  const [items, setItems] = useState<EvaluationResult[]>([]);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);
  const active = useRef(true);

  useEffect(() => {
    let cancelled = false;
    active.current = true;
    void listEvaluations(taskId, runId).then(value => {
      if (!cancelled) setItems(value);
    }).catch(cause => {
      if (!cancelled) setError(cause instanceof Error ? cause.message : "无法读取评估");
    }).finally(() => { if (!cancelled) setBusy(false); });
    return () => { cancelled = true; active.current = false; };
  }, [taskId, runId]);

  const blocked = items.some(item => item.severity === "blocking" && item.status !== "passed");
  async function evaluate() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await evaluateRun(taskId, runId);
      if (!active.current) return;
      setItems(result.evaluations);
      onChanged();
    } catch (cause) {
      if (active.current) setError(cause instanceof Error ? cause.message : "评估失败");
    } finally { if (active.current) setBusy(false); }
  }
  async function review(outcome: "accepted" | "needs_fix" | "blocked") {
    if (busy) return;
    if (!note.trim()) { setError("请填写人工复核说明"); return; }
    setBusy(true);
    setError("");
    try {
      await recordReview(taskId, runId, { outcome, note, evaluation_ids: items.map(item => item.evaluation_id), actor: "human" });
      if (active.current) onChanged();
    } catch (cause) {
      if (active.current) setError(cause instanceof Error ? cause.message : "保存复核失败");
    } finally { if (active.current) setBusy(false); }
  }

  return <section aria-label="当前运行评估" className="mt-5 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
    <div className="flex items-center justify-between"><h3 className="font-semibold">Evidence Evaluation</h3><button disabled={busy || !!decision} className="rounded bg-teal-600 px-3 py-1.5 text-xs text-white disabled:opacity-40" onClick={() => void evaluate()}>运行确定性评估</button></div>
    <p className="mt-2 break-all text-xs text-zinc-500">当前会话：{sessionId} · Run：{runId}</p>
    <p className="mt-2 text-xs text-zinc-500">已保存的评估为历史快照；补充证据或更换规则后，请创建新的 Run。</p>
    {busy && <p role="status" className="mt-2 text-xs text-zinc-500">正在读取或保存当前 Run…</p>}
    {error && <p role="alert" className="mt-2 text-xs text-red-600">{error}</p>}
    {decision && <p role="status" className="mt-3 rounded bg-zinc-100 p-3 text-xs dark:bg-zinc-900">已保存人工复核：{{ accepted: "已接受", needs_fix: "需修复", blocked: "已阻断" }[decision.outcome]} · {decision.note}</p>}
    <div className="mt-3 space-y-2">{items.map(item => <div key={item.evaluation_id} className="rounded bg-zinc-100 p-3 text-xs dark:bg-zinc-900"><p><b>{item.status}</b> · {item.summary}</p><p className="mt-1 text-zinc-500">规则 {item.evaluator_id} v{item.evaluator_version} · 证据：{item.evidence_refs.join(", ") || "缺失"}</p></div>)}</div>
    {items.length > 0 && !decision && <div className="mt-3"><textarea disabled={busy} value={note} onChange={event => setNote(event.target.value)} className="w-full rounded border border-zinc-300 bg-transparent p-2 text-sm" placeholder="人工复核说明"/><div className="mt-2 flex gap-2"><button disabled={busy || blocked} onClick={() => void review("accepted")} className="rounded bg-emerald-600 px-3 py-1.5 text-xs text-white disabled:opacity-40">接受</button><button disabled={busy} onClick={() => void review("needs_fix")} className="rounded bg-amber-600 px-3 py-1.5 text-xs text-white">需修复</button><button disabled={busy} onClick={() => void review("blocked")} className="rounded bg-red-600 px-3 py-1.5 text-xs text-white">阻断</button></div></div>}
  </section>;
}
