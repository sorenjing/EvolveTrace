import { contextDeliveryCopy } from "@/app/lib/context-receipts";
import type { ContextReceipt } from "@/app/lib/harness-types";

function IdentifierList({ title, values }: { title: string; values: string[] }) {
  return <details className="mt-2"><summary className="cursor-pointer text-xs text-zinc-500">{title}（{values.length}）</summary><ul className="mt-1 space-y-1 pl-4 font-mono text-[11px] text-zinc-500">{values.map(value => <li className="break-all" key={value}>{value}</li>)}</ul></details>;
}

export function ContextReceiptCard({ receipts }: { receipts: ContextReceipt[] }) {
  if (receipts.length === 0) {
    return <section className="mt-5 rounded-xl border border-amber-200 bg-amber-50/60 p-4 text-sm dark:border-amber-900 dark:bg-amber-950/20"><p className="font-medium text-amber-900 dark:text-amber-200">Context Delivery</p><p className="mt-1 text-amber-800 dark:text-amber-300">尚无 Context Receipt；上下文交付与执行绑定证据不完整。</p></section>;
  }
  return <section className="mt-5 rounded-xl border border-zinc-200 p-4 text-sm dark:border-zinc-800"><p className="font-medium">Context Delivery</p><div className="mt-3 space-y-3">{receipts.map(receipt => <article className="rounded-lg bg-zinc-50 p-3 dark:bg-zinc-900" key={receipt.receipt_id}><div className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium text-teal-700 dark:text-teal-300">{contextDeliveryCopy[receipt.status]}</span><time className="text-xs text-zinc-500" dateTime={receipt.updated_at}>{new Date(receipt.updated_at).toLocaleString()}</time></div><dl className="mt-2 grid gap-2 text-xs sm:grid-cols-2"><div><dt className="text-zinc-500">Platform / Adapter</dt><dd>{receipt.platform} / {receipt.adapter}</dd></div><div><dt className="text-zinc-500">Attempt</dt><dd className="break-all font-mono">{receipt.attempt_id}</dd></div><div><dt className="text-zinc-500">Bundle</dt><dd className="break-all font-mono" title={receipt.bundle_id}>{receipt.bundle_id.slice(0, 18)}</dd></div><div><dt className="text-zinc-500">Receipt</dt><dd className="break-all font-mono" title={receipt.receipt_id}>{receipt.receipt_id.slice(0, 18)}</dd></div></dl><IdentifierList title="Source IDs" values={receipt.delivered_source_ids} /><IdentifierList title="Skill IDs" values={receipt.loaded_skill_ids} /></article>)}</div></section>;
}
