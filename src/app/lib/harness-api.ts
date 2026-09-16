import type { ContextReceipt, ContextSnapshot, TaskContract, UnboundRun } from "@/app/lib/harness-types";

function apiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL ?? process.env.NEXT_PUBLIC_BACKEND_URL;
  return configured ? configured.replace(/\/$/, "") : typeof window === "undefined" ? "" : window.location.origin;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}${path}`, { ...init, headers: { Accept: "application/json", "Content-Type": "application/json", ...init?.headers } });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Harness 请求失败：HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const listTasks = () => request<TaskContract[]>("/api/harness/tasks", { cache: "no-store" });
export const getTask = (taskId: string) => request<TaskContract>(`/api/harness/tasks/${encodeURIComponent(taskId)}`, { cache: "no-store" });
export const createTask = (task: Omit<TaskContract, "task_id" | "created_at">) => request<TaskContract>("/api/harness/tasks", { method: "POST", body: JSON.stringify(task) });
export const importContextSnapshot = (bundle: object) => request<ContextSnapshot>("/api/harness/context-snapshots", { method: "POST", body: JSON.stringify(bundle) });
export const activateTask = (taskId: string, repositoryPath: string) => request<TaskContract>(`/api/harness/tasks/${encodeURIComponent(taskId)}/activate`, { method: "POST", body: JSON.stringify({ repository_path: repositoryPath }) });
export const listUnboundRuns = () => request<UnboundRun[]>("/api/harness/runs/unbound", { cache: "no-store" });
export const listContextReceipts = (taskId: string) => request<ContextReceipt[]>(`/api/harness/tasks/${encodeURIComponent(taskId)}/context-receipts`, { cache: "no-store" });
