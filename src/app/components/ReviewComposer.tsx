import { useState } from "react";
import type { AuditStep } from "@/app/lib/audit-flow";
import { reviewPrompt } from "@/app/lib/review-prompt";

export function ReviewComposer({ step }: { step: AuditStep | null }) {
  const [review, setReview] = useState("");
  const [copiedPrompt, setCopiedPrompt] = useState("");
  const [error, setError] = useState("");
  const [copying, setCopying] = useState(false);

  if (!step) return null;
  const prompt = reviewPrompt(step, review);
  const copied = copiedPrompt === prompt;

  async function copyPrompt() {
    if (!step || copying) return;
    setCopying(true); setCopiedPrompt(""); setError("");
    try {
      await navigator.clipboard.writeText(prompt);
      setCopiedPrompt(prompt);
    } catch {
      setError("复制失败，请在下方展开提示并手动复制。");
    } finally { setCopying(false); }
  }

  return (
    <div className="shrink-0 border-t border-zinc-200 p-4 dark:border-zinc-800">
      <p className="text-xs font-semibold">把审查意见交给 Agent</p>
      <textarea aria-label="针对当前步骤的审查意见" maxLength={1000} value={review} onChange={(eventChange) => setReview(eventChange.target.value)} rows={2} placeholder="例如：先核对第一处测试失败，再做最小修复并重新验证。" className="mt-2 w-full resize-none rounded-xl border border-zinc-200 bg-transparent p-3 text-xs outline-none ring-teal-500 focus:ring-2 dark:border-zinc-700" />
      <button type="button" disabled={copying} onClick={copyPrompt} className="mt-2 w-full rounded-xl bg-zinc-900 px-3 py-2 text-xs font-semibold text-white transition hover:bg-teal-700 disabled:opacity-50 dark:bg-white dark:text-zinc-900 dark:hover:bg-teal-300">
        {copying ? "复制中…" : copied ? "已复制，粘贴到 Codex 继续" : "复制修正提示（含证据）"}
      </button>
      <p role="status" className="mt-2 text-[11px] text-zinc-500">{copied ? "仅已复制，尚未发送或执行。" : "包含当前步骤的输入与输出，发送前请核对内容。"}</p>
      {error && <><p role="alert" className="mt-2 text-xs text-amber-700 dark:text-amber-300">{error}</p><details className="mt-2 text-xs"><summary className="cursor-pointer">手动复制修正提示</summary><textarea aria-label="可手动复制的修正提示" readOnly value={prompt} rows={5} className="mt-2 max-h-32 w-full overflow-auto rounded border p-2" /></details></>}
    </div>
  );
}
