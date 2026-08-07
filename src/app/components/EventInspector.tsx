import type { AuditEvent } from "@/app/lib/audit-types";

export function EventInspector({ event }: { event: AuditEvent | null }) {
  if (!event) {
    return <div className="flex h-full items-center justify-center p-6 text-center text-sm text-zinc-500">选择一个事件查看执行证据。</div>;
  }

  return (
    <div className="space-y-5 p-4">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-teal-600 dark:text-teal-400">Evidence</p>
        <h3 className="mt-1 text-lg font-semibold">事件详情</h3>
        <p className="mt-1 break-all text-xs text-zinc-500">{event.event_id}</p>
      </div>
      {event.risk_findings.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
          <p className="font-semibold">需要复核</p>
          {event.risk_findings.map((finding) => <p key={finding.code} className="mt-1">{finding.message}{finding.evidence ? `：${finding.evidence}` : ""}</p>)}
        </div>
      )}
      <Detail label="事件类型" value={event.event_type} />
      <Detail label="工具" value={event.tool_name || "无"} />
      <Detail label="轮次" value={event.turn_id || "无"} />
      <div>
        <p className="mb-2 text-xs font-medium text-zinc-500">脱敏后的输入与输出</p>
        <pre className="max-h-[32rem] overflow-auto rounded-xl bg-zinc-950 p-3 text-xs leading-5 text-zinc-200">{JSON.stringify(event.details, null, 2)}</pre>
      </div>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return <div className="flex items-center justify-between gap-4 border-b border-zinc-100 py-2 text-sm dark:border-zinc-900"><span className="text-zinc-500">{label}</span><span className="max-w-[65%] truncate text-right font-medium">{value}</span></div>;
}
