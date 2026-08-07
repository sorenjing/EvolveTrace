import type { AuditEvent } from "@/app/lib/audit-types";

const labels: Record<string, string> = {
  SessionStart: "会话开始",
  SessionEnd: "会话结束",
  UserPromptSubmit: "用户任务",
  PreToolUse: "工具准备",
  PostToolUse: "工具完成",
  PermissionRequest: "权限请求",
  Stop: "任务停止",
  SubagentStart: "子 Agent 开始",
  SubagentStop: "子 Agent 结束",
  PreCompact: "上下文压缩前",
  PostCompact: "上下文压缩后",
};

export function AuditTimeline({
  events,
  selectedId,
  onSelect,
}: {
  events: AuditEvent[];
  selectedId: string | null;
  onSelect: (event: AuditEvent) => void;
}) {
  return (
    <div className="space-y-2">
      {events.map((event) => {
        const hasRisk = event.risk_findings.length > 0;
        return (
          <button
            key={event.event_id}
            type="button"
            onClick={() => onSelect(event)}
            className={`group flex w-full gap-3 rounded-xl border p-3 text-left transition ${
              selectedId === event.event_id
                ? "border-teal-400 bg-teal-50/70 dark:border-teal-700 dark:bg-teal-950/30"
                : "border-zinc-200 bg-white hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-950 dark:hover:border-zinc-700"
            }`}
          >
            <div className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${hasRisk ? "bg-amber-500" : "bg-teal-500"}`} />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm font-semibold">{labels[event.event_type] ?? event.event_type}</span>
                <span className="font-mono text-[10px] text-zinc-400">#{event.sequence}</span>
              </div>
              <p className="mt-1 truncate text-xs text-zinc-500 dark:text-zinc-400">
                {event.tool_name || "Codex 生命周期事件"}
              </p>
              <p className="mt-2 text-[11px] text-zinc-400">{formatTime(event.timestamp)}</p>
              {hasRisk && <p className="mt-2 text-xs font-medium text-amber-700 dark:text-amber-300">{event.risk_findings[0].message}</p>}
            </div>
          </button>
        );
      })}
    </div>
  );
}

function formatTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleTimeString("zh-CN");
}
