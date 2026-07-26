import { ThemeToggle } from "@/app/components/ThemeToggle";

export function Header({
  onOpenConfig,
  configReady,
  onOpenTools,
}: {
  onOpenConfig: () => void;
  configReady: boolean;
  onOpenTools: () => void;
}) {
  return (
    <header className="flex items-center justify-between gap-2 border-b border-zinc-200 pb-4 dark:border-zinc-800">
      <div className="min-w-0">
        <h1 className="text-xl font-bold tracking-tight">EvolveLab</h1>
        <p className="mt-1 truncate text-xs text-zinc-500 dark:text-zinc-400">
          Coding Agent 可观测性与安全边界研究项目
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <ThemeToggle />
        <button
          type="button"
          onClick={onOpenTools}
          className="rounded-lg border border-zinc-300 px-3 py-1.5 text-xs font-medium transition hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
        >
          工具
        </button>
        <button
          type="button"
          onClick={onOpenConfig}
          className="flex items-center gap-2 rounded-lg border border-zinc-300 px-3 py-1.5 text-xs font-medium transition hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
        >
          <span
            className={`h-2 w-2 rounded-full ${configReady ? "bg-emerald-500" : "bg-amber-500"}`}
            title={configReady ? "已配置" : "未配置 API Key"}
          />
          设置
        </button>
      </div>
    </header>
  );
}
