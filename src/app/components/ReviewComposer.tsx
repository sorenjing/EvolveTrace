import { useState } from "react";
import type { AuditEvent } from "@/app/lib/audit-types";

export function ReviewComposer({ event }: { event: AuditEvent | null }) {
  const [review, setReview] = useState("");
  const [copied, setCopied] = useState(false);

  if (!event) return null;

  const prompt = [
    "请基于以下 EvolveTrace 审查意见继续当前任务：",
    `事件：${event.event_type}${event.tool_name ? ` / ${event.tool_name}` : ""}`,
    `事件 ID：${event.event_id}`,
    `审查意见：${review.trim() || "请先核对该步骤的执行证据与风险提示。"}`,
    "要求：先说明你将如何修正，再执行必要的修改，并在修改后运行相关验证。",
  ].join("\n");

  async function copyPrompt() {
    await navigator.clipboard.writeText(prompt);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <div className="border-t border-zinc-200 p-4 dark:border-zinc-800">
      <p className="text-xs font-semibold">针对这一步提出建议</p>
      <textarea value={review} onChange={(eventChange) => setReview(eventChange.target.value)} rows={3} placeholder="例如：这个命令修改范围过大，请先展示 diff 并补充测试。" className="mt-2 w-full resize-none rounded-xl border border-zinc-200 bg-transparent p-3 text-xs outline-none ring-teal-500 focus:ring-2 dark:border-zinc-700" />
      <button type="button" onClick={copyPrompt} className="mt-2 w-full rounded-xl bg-zinc-900 px-3 py-2 text-xs font-semibold text-white transition hover:bg-teal-700 dark:bg-white dark:text-zinc-900 dark:hover:bg-teal-300">
        {copied ? "已复制修正提示" : "复制修正提示"}
      </button>
    </div>
  );
}
