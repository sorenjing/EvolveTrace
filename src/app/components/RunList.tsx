import type { Run } from "@/app/lib/harness-types";

export function RunList({ runs, selectedId, onSelect }: { runs: Run[]; selectedId: string | null; onSelect: (id: string) => void }) {
  return <section className="mt-5"><p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-teal-600">Task Runs</p>{runs.length ? <div className="mt-2 space-y-1">{runs.map(run => <button disabled={!run.session_id} className={`w-full rounded border p-2 text-left text-xs ${selectedId === run.session_id ? "border-teal-500 bg-teal-50 dark:bg-teal-950/40" : "border-zinc-200 dark:border-zinc-800"} disabled:opacity-60`} onClick={() => run.session_id && onSelect(run.session_id)} key={run.run_id}>{run.cwd || run.run_id} · {run.status} · {run.session_id ? "evidence ready" : "waiting"}</button>)}</div> : <p className="mt-2 text-sm text-zinc-500">此 Task 还没有 Run。</p>}</section>;
}
