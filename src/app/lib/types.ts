// 共享类型、常量与配置工具函数

export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8001";

export type AgentEventType =
  | "thought"
  | "action"
  | "observation"
  | "error"
  | "complete";

export interface AgentEvent {
  type: AgentEventType;
  step: number;
  payload: Record<string, unknown>;
}

// 单个步骤聚合：一个 step 可能先后收到 thought / action / observation
export interface TimelineStep {
  step: number;
  thought?: string;
  action?: { tool: string; input: unknown };
  observation?: string;
  error?: string;
}

export type RunStatus = "idle" | "running" | "done" | "error";

export const ROLES = [
  { value: "standard", label: "标准" },
  { value: "admin", label: "管理员" },
  { value: "readonly", label: "只读" },
] as const;

// ---------- LLM 配置（localStorage 持久化，避免 .env 泄密） ----------

export interface LlmConfig {
  apiKey: string;
  baseUrl: string;
  model: string;
}

export const DEFAULT_CONFIG: LlmConfig = {
  apiKey: "",
  baseUrl: "https://open.bigmodel.cn/api/paas/v4",
  model: "glm-4-flash",
};

const CONFIG_STORAGE_KEY = "evolvelab_llm_config";

export function loadConfig(): LlmConfig {
  if (typeof window === "undefined") return DEFAULT_CONFIG;
  try {
    const raw = localStorage.getItem(CONFIG_STORAGE_KEY);
    if (!raw) return DEFAULT_CONFIG;
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return DEFAULT_CONFIG;
    return { ...DEFAULT_CONFIG, ...(parsed as Partial<LlmConfig>) };
  } catch {
    return DEFAULT_CONFIG;
  }
}

export function saveConfig(cfg: LlmConfig): void {
  try {
    localStorage.setItem(CONFIG_STORAGE_KEY, JSON.stringify(cfg));
  } catch {
    // 忽略存储失败
  }
}

// ---------- 工具元信息 ----------

export interface ToolMeta {
  name: string;
  description: string;
  args: string[];
  custom?: boolean;
}
