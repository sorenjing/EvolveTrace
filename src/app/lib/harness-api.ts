import type { EvaluationResult, ReviewDecision, RunComparison, TaskContract, UnboundRun } from "@/app/lib/harness-types";

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
export const activateTask = (taskId: string, repositoryPath: string) => request<TaskContract>(`/api/harness/tasks/${encodeURIComponent(taskId)}/activate`, { method: "POST", body: JSON.stringify({ repository_path: repositoryPath }) });
export const compareRuns = (taskId: string, originalRunId: string, correctedRunId: string) => request<RunComparison>(`/api/harness/tasks/${encodeURIComponent(taskId)}/comparisons`, { method: "POST", body: JSON.stringify({ original_run_id: originalRunId, corrected_run_id: correctedRunId }) });
export const listUnboundRuns = () => request<UnboundRun[]>("/api/harness/runs/unbound", { cache: "no-store" });
export const evaluateRun = (taskId: string, runId: string) => request<{ evaluations: EvaluationResult[] }>(`/api/harness/tasks/${encodeURIComponent(taskId)}/runs/${encodeURIComponent(runId)}/evaluate`, { method: "POST" });
export const listEvaluations = (taskId: string, runId: string) => request<EvaluationResult[]>(`/api/harness/tasks/${encodeURIComponent(taskId)}/runs/${encodeURIComponent(runId)}/evaluations`, { cache: "no-store" });
export const recordReview = (taskId: string, runId: string, payload: { outcome: ReviewDecision["outcome"]; note: string; evaluation_ids: string[]; actor: string }) => request<ReviewDecision>(`/api/harness/tasks/${encodeURIComponent(taskId)}/runs/${encodeURIComponent(runId)}/review`, { method: "POST", body: JSON.stringify(payload) });
