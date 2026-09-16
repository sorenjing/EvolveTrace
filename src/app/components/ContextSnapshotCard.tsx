import type { TaskContract } from "@/app/lib/harness-types";

export function ContextSnapshotCard({ task }: { task: TaskContract | null }) {
  const snapshot = task?.context_snapshot;
  return <section className="mt-5 rounded-xl border border-zinc-200 p-4 text-sm dark:border-zinc-800"><p className="font-medium">Context Snapshot</p>{snapshot ? <p className="mt-1 text-zinc-500">{snapshot.project} · freshness: <span className="font-medium text-teal-700 dark:text-teal-300">{snapshot.freshness}</span><br /><span className="font-mono text-xs">{snapshot.content_digest.slice(0, 12)}</span></p> : task?.context_snapshot_id ? <p className="mt-1 text-zinc-500">正在读取快照：<span className="font-mono text-xs">{task.context_snapshot_id}</span></p> : <p className="mt-1 text-zinc-500">尚未绑定上下文快照。</p>}</section>;
}
