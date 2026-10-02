import type { AuditStep } from "@/app/lib/audit-flow";

const labels: Record<string, string> = {
  SessionStart: "会话开始", SessionEnd: "会话结束", UserPromptSubmit: "用户任务",
  PermissionRequest: "权限请求", Stop: "任务停止", SubagentStart: "子 Agent 开始",
  SubagentStop: "子 Agent 结束", PreCompact: "上下文压缩前", PostCompact: "上下文压缩后",
};

function preview(step: AuditStep): string {
  const input = step.input;
  if (input && typeof input === "object" && !Array.isArray(input)) {
    const fields = input as Record<string, unknown>;
    for (const key of ["command", "patch", "input", "path", "file_path"]) {
      if (typeof fields[key] === "string" && fields[key]) return fields[key].split("\n")[0];
    }
  }
  if (typeof input === "string") return input.split("\n")[0];
  if (typeof step.event.details.prompt === "string") return step.event.details.prompt.split("\n")[0];
  return step.event.tool_name || "Codex 生命周期事件";
}

export function AuditTimeline({ steps, selectedId, onSelect }: {
  steps: AuditStep[]; selectedId: string | null; onSelect: (step: AuditStep) => void;
}) {
  return <section aria-label="执行流程" className="space-y-2">
    <div className="mb-3 flex items-end justify-between gap-3">
      <div><h2 className="text-base font-semibold">执行流程</h2><p className="text-xs text-zinc-500">按发生顺序排列；点击一步查看已采集的证据。</p></div>
      <span className="shrink-0 text-xs text-zinc-500">{steps.length} 步</span>
    </div>
    {steps.map((step, index) => {
      const event = step.event;
      const hasRisk = (step.start?.risk_findings?.length ?? 0) + (step.completion?.risk_findings?.length ?? 0) + (!step.start && !step.completion ? event.risk_findings?.length ?? 0 : 0) > 0;
      const isTool = !!step.start || !!step.completion;
      const state = isTool ? step.completion ? "已完成" : "未采集到返回" : "记录";
      const summary = preview(step);
      return <button key={step.id} type="button" onClick={() => onSelect(step)}
        aria-current={selectedId === step.id ? "step" : undefined}
        className={`flex w-full gap-3 rounded-xl border p-3 text-left transition ${selectedId === step.id ? "border-teal-500 bg-teal-50 dark:border-teal-700 dark:bg-teal-950/30" : "border-zinc-200 bg-white hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-950 dark:hover:border-zinc-700"}`}>
        <span className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold ${hasRisk ? "bg-amber-100 text-amber-800" : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300"}`}>{index + 1}</span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center justify-between gap-1"><span className="text-sm font-semibold">{isTool ? `工具 · ${event.tool_name || "未知工具"}` : labels[event.event_type] ?? event.event_type}</span><span className="text-[11px] text-zinc-500">{state}</span></span>
          <span className="mt-1 block truncate text-xs text-zinc-600 dark:text-zinc-400" title={summary}>{summary}</span>
          <span className="mt-2 block text-[11px] text-zinc-400">{new Date(step.start?.timestamp ?? event.timestamp).toLocaleTimeString("zh-CN")} · #{step.start?.sequence ?? event.sequence}{hasRisk ? " · 需复核" : ""}</span>
        </span>
      </button>;
    })}
  </section>;
}
