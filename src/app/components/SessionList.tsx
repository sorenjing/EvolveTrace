import type { AuditSessionSummary } from "@/app/lib/audit-types";

export function SessionList({
  sessions,
  selectedId,
  onSelect,
}: {
  sessions: AuditSessionSummary[];
  selectedId: string | null;
  onSelect: (sessionId: string) => void;
}) {
  return (
    <aside className="flex min-h-0 flex-col border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950 lg:border-r lg:border-b-0">
      <div className="border-b border-zinc-200 px-4 py-4 dark:border-zinc-800">
        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-teal-600 dark:text-teal-400">
          Sessions
        </p>
        <h2 className="mt-1 text-lg font-semibold">执行会话</h2>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {sessions.length === 0 ? (
          <div className="px-3 py-8 text-sm leading-6 text-zinc-500">
            还没有审计记录。安装插件后，Codex 的下一次任务会出现在这里。
          </div>
        ) : (
          sessions.map((session) => (
            <button
              key={session.session_id}
              type="button"
              onClick={() => onSelect(session.session_id)}
              className={`mb-1 w-full rounded-xl p-3 text-left transition ${
                selectedId === session.session_id
                  ? "bg-teal-50 text-teal-950 ring-1 ring-teal-200 dark:bg-teal-950/50 dark:text-teal-50 dark:ring-teal-900"
                  : "hover:bg-zinc-100 dark:hover:bg-zinc-900"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-sm font-medium">
                  {session.session_id.slice(0, 18)}
                </span>
                {session.risk_count > 0 && (
                  <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                    {session.risk_count} 风险
                  </span>
                )}
              </div>
              <p className="mt-1 truncate text-xs text-zinc-500 dark:text-zinc-400">
                {session.cwd || "本地项目"}
              </p>
              <p className="mt-2 text-[11px] text-zinc-400">
                {session.event_count} 个事件 · {formatTime(session.last_seen)}
              </p>
            </button>
          ))
        )}
      </div>
    </aside>
  );
}

function formatTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN");
}
