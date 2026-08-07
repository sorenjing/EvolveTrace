import type {
  AuditSession,
  AuditSessionSummary,
  AuditStreamMessage,
} from "@/app/lib/audit-types";
import { BACKEND_URL } from "@/app/lib/types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BACKEND_URL}${path}`, {
    ...init,
    headers: { Accept: "application/json", ...init?.headers },
  });
  if (!response.ok) {
    throw new Error(`审计服务请求失败：HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function fetchSessions(): Promise<AuditSessionSummary[]> {
  return request<AuditSessionSummary[]>("/api/audit/sessions", {
    cache: "no-store",
  });
}

export function fetchSession(sessionId: string): Promise<AuditSession> {
  return request<AuditSession>(
    `/api/audit/sessions/${encodeURIComponent(sessionId)}`,
    { cache: "no-store" },
  );
}

export function subscribeToAuditStream(
  sessionId: string | null,
  onMessage: (message: AuditStreamMessage) => void,
  onError: () => void,
): () => void {
  const query = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
  const source = new EventSource(`${BACKEND_URL}/api/audit/stream${query}`);
  source.onmessage = (event) => {
    try {
      onMessage(JSON.parse(event.data) as AuditStreamMessage);
    } catch {
      onError();
    }
  };
  source.onerror = onError;
  return () => source.close();
}
