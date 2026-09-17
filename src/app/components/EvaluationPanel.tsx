"use client";

import { useEffect, useState } from "react";
import { evaluateRun, listEvaluations, recordReview } from "@/app/lib/harness-api";
import type { EvaluationResult, TaskContract } from "@/app/lib/harness-types";

export function EvaluationPanel({ task, onChanged }: { task: TaskContract | null; onChanged: () => void }) {
  const run = task?.runs?.find(item => item.status === "completed" || item.status === "blocked");
  const [items, setItems] = useState<EvaluationResult[]>([]); const [note, setNote] = useState(""); const [error, setError] = useState("");
  useEffect(() => { if (task && run) void listEvaluations(task.task_id, run.run_id).then(setItems).catch(cause => setError(cause instanceof Error ? cause.message : "无法读取评估")); }, [task, run]);
  if (!task || !run) return null;
  const blocked = items.some(item => item.severity === "blocking" && item.status !== "passed");
  async function evaluate() { try { setError(""); setItems((await evaluateRun(task!.task_id, run!.run_id)).evaluations); onChanged(); } catch (cause) { setError(cause instanceof Error ? cause.message : "评估失败"); } }
  async function review(outcome: "accepted" | "needs_fix" | "blocked") { if (!note.trim()) { setError("请填写人工复核说明"); return; } try { await recordReview(task!.task_id, run!.run_id, { outcome, note, evaluation_ids: items.map(item => item.evaluation_id), actor: "human" }); onChanged(); } catch (cause) { setError(cause instanceof Error ? cause.message : "保存复核失败"); } }
  return <section className="mt-5 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800"><div className="flex items-center justify-between"><h3 className="font-semibold">Evidence Evaluation</h3><button className="rounded bg-teal-600 px-3 py-1.5 text-xs text-white" onClick={() => void evaluate()}>运行确定性评估</button></div>{error && <p className="mt-2 text-xs text-red-600">{error}</p>}<div className="mt-3 space-y-2">{items.map(item => <div key={item.evaluation_id} className="rounded bg-zinc-100 p-3 text-xs dark:bg-zinc-900"><p><b>{item.status}</b> · {item.summary}</p><p className="mt-1 text-zinc-500">证据：{item.evidence_refs.join(", ") || "缺失"}</p></div>)}</div>{items.length > 0 && <div className="mt-3"><textarea value={note} onChange={event => setNote(event.target.value)} className="w-full rounded border border-zinc-300 bg-transparent p-2 text-sm" placeholder="人工复核说明"/><div className="mt-2 flex gap-2"><button disabled={blocked} onClick={() => void review("accepted")} className="rounded bg-emerald-600 px-3 py-1.5 text-xs text-white disabled:opacity-40">接受</button><button onClick={() => void review("needs_fix")} className="rounded bg-amber-600 px-3 py-1.5 text-xs text-white">需修复</button><button onClick={() => void review("blocked")} className="rounded bg-red-600 px-3 py-1.5 text-xs text-white">阻断</button></div></div>}</section>;
}
