import type { AuditSession } from "@/app/lib/audit-types";

export function SessionSummary({ session }: { session: AuditSession }) {
  const cards = [
    ["事件", session.event_count, "工具与生命周期记录"],
    ["工具调用", session.tool_call_count, "可追溯的本地动作"],
    ["修改文件", session.modified_file_count, "从事件证据中提取"],
    ["风险", session.risk_count, session.risk_count ? "需要人工复核" : "暂无规则命中"],
  ];

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {cards.map(([label, value, hint]) => (
        <div key={label} className="rounded-xl border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-950">
          <p className="text-xs text-zinc-500">{label}</p>
          <p className="mt-1 text-2xl font-semibold tracking-tight">{value}</p>
          <p className="mt-1 text-[10px] text-zinc-400">{hint}</p>
        </div>
      ))}
    </div>
  );
}
