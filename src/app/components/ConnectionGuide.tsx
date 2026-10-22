import type { CaptureStatus } from "@/app/lib/activity-types";

const docs = "https://github.com/sorenjing/EvolveTrace/blob/master/docs/";
const linkClass = "text-teal-700 underline dark:text-teal-300";

export function ConnectionGuide({ capture, error }: { capture: CaptureStatus | null; error: string }) {
  const current = error ? null : capture;
  const received = current ? current.received_event_count > 0 : false;
  const history = current ? current.stored_event_count > 0 : false;
  const registered = current ? current.registered_project_count > 0 : false;
  return <details open={!!error || (!!current && (!history || !registered))} className="mt-3 rounded-lg border border-zinc-200 p-3 text-xs dark:border-zinc-800">
    <summary className="cursor-pointer font-medium">首次接入与 Agent 反馈 · {error ? "状态待核对" : !current ? "读取中" : !history ? "等待第一条执行记录" : !registered ? "待登记项目" : received ? "本次启动已收件" : "有历史记录，等待新事件"}</summary>
    <ol className="mt-3 space-y-3 leading-5">
      <li><b>1. 本地服务：{current ? "状态接口可访问" : "待确认"}</b><p className="text-zinc-500">{error || "页面打开不等于插件已启用；下方只说明本服务实际收到的事件。"}</p></li>
      <li><b>2. 执行事件：{!current ? "待确认" : received ? `本次启动收到 ${current.received_event_count} 条` : history ? "仅有历史记录" : "尚未收到"}</b>
        <p className="text-zinc-500">安装并启用统一插件后，按客户端要求审核 Hook。在目标项目新开 Codex 会话，运行一次只读命令（如 git status），再刷新并核对新会话及输入输出。无新事件可能只是空闲；收件也不证明 Hook 信任状态或覆盖完整。</p>
        <a className={linkClass} href={`${docs}consolidation.md`} target="_blank" rel="noopener noreferrer">插件安装步骤</a><span className="mx-2">·</span><a className={linkClass} href={`${docs}observability.md`} target="_blank" rel="noopener noreferrer">没有事件时排查</a>
      </li>
      <li><b>3. 项目归属：{!current ? "待确认" : registered ? `已登记 ${current.registered_project_count} 个项目` : "尚未登记"}</b>
        <p className="text-zinc-500">在已配置 .aictx.toml 的工作区运行下列命令，替换两个占位值；登记后再从左侧选择目标项目与会话。未登记时仍可查看未归属会话。</p>
        <code className="mt-1 block break-words rounded bg-zinc-50 p-2 dark:bg-zinc-900">aictx audit sync --workspace &lt;工作区目录&gt; --evolvetrace-url &lt;当前服务地址&gt;</code>
      </li>
      <li><b>4. 把问题反馈给 Agent</b><p className="text-zinc-500">定位证据 → 在右侧写审查意见 → 复制含证据的修正提示 → 粘贴到 Codex。复制不会发送或执行。修正后回到工作台核对新证据；使用 Task 时，先准备修正运行，再新开会话，并按原验收条件评估。</p>
        <p className="mt-1 text-zinc-500">长期复用的结论经人工确认后保存为项目记忆；需要显式启用 Context 回读，且加载记录不能证明模型采用。</p>
        <a className={linkClass} href={`${docs}usage.md`} target="_blank" rel="noopener noreferrer">完整复核流程</a><span className="mx-2">·</span><a className={linkClass} href={`${docs}workspace-audit.md`} target="_blank" rel="noopener noreferrer">启用记忆回读</a>
      </li>
    </ol>
  </details>;
}
