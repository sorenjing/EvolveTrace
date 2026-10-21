import type { TaskContract, UnboundRun } from "@/app/lib/harness-types";
import type { ActivityProject } from "@/app/lib/activity-types";

const taskStatuses: Record<string, string> = { draft: "草稿", ready: "待执行", active: "执行中", needs_review: "待复核", needs_fix: "需修复", accepted: "已接受", blocked: "已阻断" };
const selectedClass = "bg-teal-50 text-teal-950 dark:bg-teal-950/40 dark:text-teal-50";
const idleClass = "hover:bg-zinc-100 dark:hover:bg-zinc-900";

export function TaskList({ projects, selectedProjectId, onSelectProject, tasks, unboundRuns, selectedTaskId, selectedSessionId, onSelectTask, onSelectUnbound }: {
  projects: ActivityProject[]; selectedProjectId: string | null; onSelectProject: (id: string | null) => void;
  tasks: TaskContract[]; unboundRuns: UnboundRun[]; selectedTaskId: string | null;
  selectedSessionId: string | null; onSelectTask: (id: string) => void; onSelectUnbound: (id: string) => void;
}) {
  const attributed = new Set(projects.flatMap(project => project.sessions?.map(session => session.session_id) ?? []));
  const otherSessions = unboundRuns.filter(session => !attributed.has(session.session_id));
  return <nav aria-label="项目与会话导航" className="border-b border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950 lg:border-b-0 lg:border-r">
    <p className="mb-1 text-sm font-semibold">项目与会话</p>
    <p className="mb-4 text-xs leading-5 text-zinc-500">先选项目，再查看某次会话。路径用于说明归属，不是文件目录树。</p>
    <button type="button" aria-pressed={!selectedProjectId && !selectedSessionId && !selectedTaskId} className={`mb-3 w-full rounded-lg p-3 text-left text-sm ${!selectedProjectId && !selectedSessionId && !selectedTaskId ? selectedClass : idleClass}`} onClick={() => onSelectProject(null)}>全部项目总览</button>
    <ul className="space-y-2">{projects.toSorted((a, b) => b.activity.attempt_count - a.activity.attempt_count).map(project => <li key={project.project_id}>
      <button type="button" aria-pressed={selectedProjectId === project.project_id} className={`w-full rounded-lg p-3 text-left text-sm ${selectedProjectId === project.project_id ? selectedClass : idleClass}`} onClick={() => onSelectProject(project.project_id)}>
        <span className="block font-medium">{project.name}{!project.active && <span className="ml-1 text-xs text-zinc-500">历史</span>}</span>
        <span className="mt-1 block truncate text-xs text-zinc-500" title={project.relative_path}>{project.relative_path}</span>
        <span className="mt-1 block text-xs text-zinc-500">{project.session_count} 个会话 · {project.activity.attempt_count} 次调用</span>
      </button>
      {selectedProjectId === project.project_id && <div className="ml-3 mt-1 max-h-80 space-y-1 overflow-y-auto border-l border-teal-200 pl-2 dark:border-teal-900">
        {project.sessions?.length ? project.sessions.map(session => <button type="button" key={session.session_id} aria-pressed={selectedSessionId === session.session_id} className={`w-full rounded-lg p-2 text-left text-xs ${selectedSessionId === session.session_id ? selectedClass : idleClass}`} onClick={() => onSelectUnbound(session.session_id)}>
          <span className="block font-medium">会话 {session.session_id.slice(0, 8)}</span><span className="mt-1 block text-zinc-500">{new Date(session.last_seen).toLocaleString("zh-CN")} · {session.event_count} 条事件</span>
        </button>) : <p className="p-2 text-xs text-zinc-500">当前采集范围内暂无会话。</p>}
      </div>}
    </li>)}</ul>
    {!projects.length && <p className="text-xs leading-5 text-zinc-500">项目列表加载后显示；尚未登记项目时，也可从下方查看已采集会话。</p>}
    <details className="mt-5 border-t border-zinc-200 pt-4 dark:border-zinc-800"><summary className="cursor-pointer text-xs font-medium">其他会话（{otherSessions.length}）</summary>
      <p className="my-2 text-xs leading-5 text-zinc-500">当前统计范围内尚未找到项目归属的会话；不表示命令执行失败。</p>
      <div className="max-h-64 overflow-y-auto">{otherSessions.map(run => <button type="button" key={run.session_id} className={`mb-1 w-full rounded-lg p-2 text-left text-xs ${selectedSessionId === run.session_id ? selectedClass : idleClass}`} onClick={() => onSelectUnbound(run.session_id)}>
        <span className="block font-medium">会话 {run.session_id.slice(0, 8)}</span><span className="mt-1 block truncate text-zinc-500" title={run.cwd}>{run.cwd || "未提供工作目录"}</span><span className="mt-1 block text-zinc-500">{new Date(run.first_seen).toLocaleString("zh-CN")}</span>
      </button>)}</div>
    </details>
    <details open={!!selectedTaskId} className="mt-5 border-t border-zinc-200 pt-4 dark:border-zinc-800"><summary className="cursor-pointer text-xs font-medium">任务验收 · 进阶（{tasks.length}）</summary>
      <p className="my-2 text-xs leading-5 text-zinc-500">按任务目标和验收条件复核多次执行。仅查看命令统计，无需创建任务。</p>
      {tasks.length ? tasks.map(task => <button type="button" key={task.task_id} className={`mb-1 w-full rounded-lg p-3 text-left text-sm ${selectedTaskId === task.task_id ? selectedClass : idleClass}`} onClick={() => onSelectTask(task.task_id)}><span className="block font-medium">{task.title}</span><span className="mt-1 block text-xs text-zinc-500">{taskStatuses[task.status] ?? task.status}</span></button>) : <p className="text-xs text-zinc-500">暂无验收任务。可通过 Context CLI 准备并提交 Task。</p>}
    </details>
  </nav>;
}
