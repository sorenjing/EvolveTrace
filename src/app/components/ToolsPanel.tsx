"use client";

import { useState, useCallback, useEffect } from "react";
import { BACKEND_URL, type ToolMeta } from "@/app/lib/types";

export function ToolsPanel() {
  const [builtin, setBuiltin] = useState<ToolMeta[]>([]);
  const [custom, setCustom] = useState<ToolMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const resp = await fetch(`${BACKEND_URL}/api/tools`);
      const data = await resp.json();
      setBuiltin(data.builtin ?? []);
      setCustom(data.custom ?? []);
    } catch {
      // 忽略
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // 延后到微任务，避免在 effect 内同步触发 setState（eslint react-hooks）
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      void refresh();
    });
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  const handleDelete = useCallback(async (name: string) => {
    setDeleting(name);
    try {
      await fetch(`${BACKEND_URL}/api/tools/${name}`, { method: "DELETE" });
      await refresh();
    } finally {
      setDeleting(null);
    }
  }, [refresh]);

  return (
    <section className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm font-semibold">工具列表</p>
        <button
          type="button"
          onClick={refresh}
          className="text-xs text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
        >
          刷新
        </button>
      </div>
      {loading ? (
        <p className="text-sm text-zinc-500">加载中...</p>
      ) : (
        <div className="flex flex-col gap-4">
          <div>
            <p className="mb-2 text-xs font-medium text-zinc-500">
              内置工具 ({builtin.length})
            </p>
            <div className="flex flex-col gap-1.5">
              {builtin.map((t) => (
                <ToolItem key={t.name} tool={t} />
              ))}
            </div>
          </div>
          <div>
            <p className="mb-2 text-xs font-medium text-zinc-500">
              自定义工具 ({custom.length})
              {custom.length === 0 && " · Agent 创建后会显示在这里"}
            </p>
            <div className="flex flex-col gap-1.5">
              {custom.length === 0 ? (
                <p className="text-xs text-zinc-400">暂无自定义工具</p>
              ) : (
                custom.map((t) => (
                  <ToolItem
                    key={t.name}
                    tool={t}
                    onDelete={handleDelete}
                    deleting={deleting === t.name}
                  />
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function ToolItem({
  tool,
  onDelete,
  deleting,
}: {
  tool: ToolMeta;
  onDelete?: (name: string) => void;
  deleting?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-2 rounded-lg border border-zinc-200 px-3 py-2 dark:border-zinc-800">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-medium">{tool.name}</span>
          {tool.custom && (
            <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 dark:bg-amber-950 dark:text-amber-300">
              自定义
            </span>
          )}
        </div>
        <p className="mt-0.5 line-clamp-2 text-xs text-zinc-500 dark:text-zinc-400">
          {tool.description}
        </p>
        {tool.args.length > 0 && (
          <p className="mt-0.5 font-mono text-[10px] text-zinc-400">
            args: {tool.args.join(", ")}
          </p>
        )}
      </div>
      {onDelete && (
        <button
          type="button"
          onClick={() => onDelete(tool.name)}
          disabled={deleting}
          className="shrink-0 text-xs text-red-500 hover:text-red-700 disabled:opacity-50"
        >
          {deleting ? "删除中" : "删除"}
        </button>
      )}
    </div>
  );
}
