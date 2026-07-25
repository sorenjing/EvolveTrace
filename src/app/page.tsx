"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import {
  BACKEND_URL,
  type AgentEvent,
  type TimelineStep,
  type RunStatus,
  type LlmConfig,
  DEFAULT_CONFIG,
  loadConfig,
  saveConfig,
} from "@/app/lib/types";
import { Header } from "@/app/components/Header";
import { ConfigPanel } from "@/app/components/ConfigPanel";
import { ToolsPanel } from "@/app/components/ToolsPanel";
import { InputArea } from "@/app/components/InputArea";
import { Timeline } from "@/app/components/Timeline";
import { TaskTemplates } from "@/app/components/TaskTemplates";

export default function Home() {
  const [task, setTask] = useState("");
  const [role, setRole] = useState<string>("standard");
  const [steps, setSteps] = useState<TimelineStep[]>([]);
  const [status, setStatus] = useState<RunStatus>("idle");
  const [finalResult, setFinalResult] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string>("");

  // LLM 配置（localStorage 持久化）
  const [config, setConfig] = useState<LlmConfig>(DEFAULT_CONFIG);
  const [showConfig, setShowConfig] = useState(false);
  const [showTools, setShowTools] = useState(false);
  const configLoaded = useRef(false);

  // 首次挂载从 localStorage 加载配置
  useEffect(() => {
    if (configLoaded.current) return;
    configLoaded.current = true;
    setConfig(loadConfig());
  }, []);

  // 用于中断 fetch
  const abortRef = useRef<AbortController | null>(null);
  // 同步 status，供 SSE 回调判断（避免 complete 覆盖 error）
  const statusRef = useRef<RunStatus>("idle");
  statusRef.current = status;

  // 将事件聚合到对应 step
  const applyEvent = useCallback((ev: AgentEvent) => {
    if (ev.type === "complete") {
      // 若已处于 error（死循环/LLM 失败），忽略随后的 complete，避免成功态覆盖失败
      if (statusRef.current === "error") return;
      const result =
        typeof ev.payload.result === "string" ? ev.payload.result : "";
      setFinalResult(result);
      statusRef.current = "done";
      setStatus("done");
      return;
    }
    if (ev.type === "error") {
      const msg =
        typeof ev.payload.message === "string" ? ev.payload.message : "未知错误";
      setErrorMsg(msg);
      statusRef.current = "error";
      setStatus("error");
      // 同时把错误填入对应 step，让 Timeline 显示失败状态色
      if (ev.step !== undefined) {
        setSteps((prev) => {
          const idx = prev.findIndex((s) => s.step === ev.step);
          if (idx === -1) {
            return [...prev, { step: ev.step, error: msg }];
          }
          const copy = [...prev];
          copy[idx] = { ...copy[idx], error: msg };
          return copy;
        });
      }
      return;
    }

    setSteps((prev) => {
      const idx = prev.findIndex((s) => s.step === ev.step);
      if (idx === -1) {
        // 新 step
        const next: TimelineStep = { step: ev.step };
        fillStep(next, ev);
        return [...prev, next];
      }
      const copy = [...prev];
      copy[idx] = { ...copy[idx] };
      fillStep(copy[idx], ev);
      return copy;
    });
  }, []);

  const runAgent = useCallback(async () => {
    if (!task.trim() || status === "running") return;

    // 检查 API Key 是否已配置
    if (!config.apiKey.trim()) {
      setErrorMsg("请先配置 LLM API Key（点击右上角「设置」按钮）");
      setShowConfig(true);
      return;
    }

    // 重置状态
    setSteps([]);
    setFinalResult("");
    setErrorMsg("");
    setStatus("running");

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const resp = await fetch(`${BACKEND_URL}/api/agent/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task: task.trim(),
          role,
          api_key: config.apiKey,
          base_url: config.baseUrl,
          model: config.model,
        }),
        signal: controller.signal,
      });

      if (!resp.ok || !resp.body) {
        throw new Error(`后端响应异常: HTTP ${resp.status}`);
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // SSE 事件以空行分隔
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";

        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data: ")) continue;
          const data = line.slice(6);
          if (data === "[DONE]") {
            // 流正常结束；若未收到 complete 事件，标记为 done
            setStatus((s) => (s === "running" ? "done" : s));
            return;
          }
          try {
            const ev = JSON.parse(data) as AgentEvent;
            applyEvent(ev);
          } catch {
            // 忽略无法解析的行
          }
        }
      }
    } catch (e: unknown) {
      if (e instanceof DOMException && e.name === "AbortError") {
        setStatus("idle");
        return;
      }
      const msg = e instanceof Error ? e.message : String(e);
      setErrorMsg(msg);
      setStatus("error");
    } finally {
      abortRef.current = null;
    }
  }, [task, role, status, applyEvent, config]);

  const stopAgent = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const running = status === "running";

  return (
    <div className="min-h-screen w-full bg-zinc-50 text-zinc-900 dark:bg-black dark:text-zinc-100">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-4 px-4 py-6 sm:gap-6 sm:py-8">
        <Header
          onOpenConfig={() => setShowConfig((v) => !v)}
          configReady={!!config.apiKey.trim()}
          onOpenTools={() => setShowTools((v) => !v)}
        />

        {showConfig && (
          <ConfigPanel
            config={config}
            onChange={setConfig}
            onSave={() => {
              saveConfig(config);
              setShowConfig(false);
            }}
          />
        )}

        {showTools && <ToolsPanel />}

        <InputArea
          task={task}
          role={role}
          running={running}
          onTaskChange={setTask}
          onRoleChange={setRole}
          onRun={runAgent}
          onStop={stopAgent}
        />

        {steps.length === 0 && status === "idle" && (
          <TaskTemplates onPick={setTask} disabled={running} />
        )}

        {errorMsg && (
          <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
            <p className="font-semibold">出错</p>
            <p className="mt-1 whitespace-pre-wrap break-all">{errorMsg}</p>
          </div>
        )}

        <Timeline steps={steps} />

        {finalResult && (
          <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-4 dark:border-emerald-900 dark:bg-emerald-950">
            <p className="mb-2 text-sm font-semibold text-emerald-700 dark:text-emerald-300">
              最终结果
            </p>
            <p className="whitespace-pre-wrap break-words text-sm text-emerald-900 dark:text-emerald-100">
              {finalResult}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------- 辅助：将事件字段填入 step ----------

function fillStep(step: TimelineStep, ev: AgentEvent): void {
  switch (ev.type) {
    case "thought":
      step.thought = typeof ev.payload.content === "string" ? ev.payload.content : "";
      break;
    case "action":
      step.action = {
        tool: typeof ev.payload.tool === "string" ? ev.payload.tool : "",
        input: ev.payload.input,
      };
      break;
    case "observation":
      step.observation =
        typeof ev.payload.result === "string" ? ev.payload.result : "";
      break;
  }
}
