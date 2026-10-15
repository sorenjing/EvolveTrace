import type { ActivityCode, ActivityFinding, ActivityReport, AuditMemory, AuditMemoryEntry, CaptureStatus } from "./activity-types";

async function request<T>(path: string, payload?: object, signal?: AbortSignal): Promise<T> {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL ?? process.env.NEXT_PUBLIC_BACKEND_URL;
  const origin = configured?.replace(/\/$/, "") ?? "";
  const response = await fetch(`${origin}/api/activity${path}`, {
    method: payload ? "POST" : "GET", cache: "no-store", signal,
    headers: { Accept: "application/json", ...(payload ? { "Content-Type": "application/json" } : {}) },
    body: payload ? JSON.stringify(payload) : undefined,
  });
  if (!response.ok) throw new Error(`项目审计请求失败：HTTP ${response.status}`);
  return response.json() as Promise<T>;
}

export const fetchActivity = (signal?: AbortSignal) => request<ActivityReport>("/report", undefined, signal);
export const fetchCaptureStatus = (signal?: AbortSignal) => request<CaptureStatus>("/status", undefined, signal);
export const fetchAuditMemory = (projectId: string, signal?: AbortSignal) => request<AuditMemory>(`/memory/${encodeURIComponent(projectId)}`, undefined, signal);
export const reviewActivity = (projectId: string, finding: ActivityFinding, action: "ignore" | "mute") => request("/decisions", {
  project_id: projectId, session_id: finding.session_id, finding_id: finding.finding_id, code: finding.code, action,
});
export const unmuteActivity = (projectId: string, code: ActivityCode) => request("/decisions", { project_id: projectId, code, action: "unmute" });
export const saveAuditMemory = (projectId: string, finding: ActivityFinding, note: string) => request<AuditMemoryEntry>("/memory", {
  project_id: projectId, session_id: finding.session_id, evidence_refs: finding.evidence_refs, note, confirmed: true,
});
