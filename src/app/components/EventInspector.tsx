import type { AuditStep } from "@/app/lib/audit-flow";
import { formatEvidence } from "@/app/lib/audit-flow";

const fieldLabels: Record<string, string> = {
  command: "命令", patch: "补丁", input: "输入内容", path: "路径", file_path: "文件路径",
  stdout: "标准输出", stderr: "错误输出", exit_code: "退出码", output: "输出内容",
  status: "状态", duration_ms: "耗时（毫秒）",
};

function Evidence({ title, value, missing }: { title: string; value: unknown; missing: string }) {
  if (value === undefined) return <div className="rounded-xl border border-dashed border-zinc-300 p-3 dark:border-zinc-700"><h4 className="text-sm font-semibold">{title}</h4><p className="mt-2 text-xs text-zinc-500">{missing}</p></div>;
  const fields = value && typeof value === "object" && !Array.isArray(value) ? Object.entries(value as Record<string, unknown>) : null;
  return <section className="rounded-xl border border-zinc-200 p-3 dark:border-zinc-800">
    <h4 className="text-sm font-semibold">{title}</h4>
    {fields ? fields.length ? <div className="mt-3 space-y-3">{fields.map(([key, item]) => <div key={key}><p className="mb-1 text-xs font-medium text-zinc-500">{fieldLabels[key] ?? key}</p><pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-zinc-100 p-2 text-xs leading-5 text-zinc-800 dark:bg-zinc-900 dark:text-zinc-200">{formatEvidence(item)}</pre></div>)}</div> : <p className="mt-2 text-xs text-zinc-500">（空对象）</p>
      : <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-zinc-100 p-2 text-xs leading-5 text-zinc-800 dark:bg-zinc-900 dark:text-zinc-200">{formatEvidence(value)}</pre>}
  </section>;
}

export function EventInspector({ step }: { step: AuditStep | null }) {
  if (!step) return <div className="flex h-full items-center justify-center p-6 text-center text-sm text-zinc-500">选择一个步骤查看输入、输出和风险。</div>;
  const event = step.event;
  const isTool = !!step.start || !!step.completion;
  const findings = [...(step.start?.risk_findings ?? []), ...(step.completion?.risk_findings ?? []), ...(!isTool ? event.risk_findings ?? [] : [])];
  const otherDetails = Object.fromEntries(Object.entries(event.details).filter(([key]) => !["tool_input", "tool_response", "tool_use_id"].includes(key)));
  return <div className="space-y-4 p-4">
    <div><p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-teal-600 dark:text-teal-400">Execution evidence</p><h3 className="mt-1 text-lg font-semibold">{isTool ? event.tool_name || "工具调用" : event.event_type}</h3><p className="mt-1 text-xs text-zinc-500">{isTool ? step.completion ? "工具已返回" : "已记录工具开始，未采集到完成事件" : "生命周期记录"}</p></div>
    {findings.length > 0 && <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100"><p className="font-semibold">需要复核</p>{findings.map((finding, index) => <p key={`${finding.code}-${index}`} className="mt-1">{finding.message}{finding.evidence ? `：${finding.evidence}` : ""}</p>)}</div>}
    {isTool ? <><Evidence title="工具输入" value={step.input} missing="Hook 未提供工具输入。" /><Evidence title="工具输出" value={step.output} missing={step.completion ? "返回事件中没有输出字段。" : "尚未收到工具完成事件；也可能是 Hook 没有上报。"} /></> : <Evidence title="事件内容" value={Object.keys(otherDetails).length ? otherDetails : undefined} missing="此事件没有额外内容。" />}
    <div className="space-y-1 border-t border-zinc-200 pt-3 text-xs text-zinc-500 dark:border-zinc-800"><p>轮次：{event.turn_id || "未提供"}</p><p>开始：{step.start?.timestamp ?? event.timestamp}</p>{step.completion && <p>完成：{step.completion.timestamp}</p>}<p className="break-all">事件 ID：{step.start?.event_id ?? event.event_id}</p></div>
    {isTool && Object.keys(otherDetails).length > 0 && <details className="text-xs text-zinc-500"><summary className="cursor-pointer">其他采集字段</summary><pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-zinc-100 p-2 dark:bg-zinc-900">{JSON.stringify(otherDetails, null, 2)}</pre></details>}
    <p className="text-xs text-zinc-500">内容已按采集规则脱敏；这里只展示 Hook 实际提供的证据，不包含隐藏推理或未上报的步骤。</p>
  </div>;
}
