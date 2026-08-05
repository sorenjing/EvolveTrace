# EvolveTrace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 EvolveLab 重构为本地优先的 Codex 执行审查与可观测插件 EvolveTrace。

**Architecture:** Codex lifecycle hooks 将脱敏事件发送到 FastAPI；后端用 SQLite 持久化并通过 SSE 发布；Next.js 工作台按会话展示执行轨迹、风险和审查反馈。

**Tech Stack:** Python 3.10、FastAPI、SQLite、pytest、Next.js 16、React 19、TypeScript、Tailwind CSS v4、Codex Hooks。

## Global Constraints

- 服务和数据默认仅限本机，不引入云服务。
- Hook 失败不得阻断 Codex。
- 不保存原始 payload，不展示或推断隐藏思维链。
- 继续保持路由薄、业务逻辑位于 `backend/services/`。
- 前端修改前遵循仓库内 Next.js 16 文档。
- 不新增前端测试框架；以 lint、类型检查和生产构建验证。

---

### Task 1: 审计协议与脱敏规则

**Files:**
- Create: `backend/audit/models.py`
- Create: `backend/audit/redaction.py`
- Create: `backend/audit/__init__.py`
- Test: `backend/tests/test_audit_redaction.py`

**Interfaces:**
- Produces: `AuditEvent.from_hook(payload: dict) -> AuditEvent`
- Produces: `redact_value(value: object) -> object`

- [ ] 编写失败测试，覆盖敏感键、Bearer Token、普通字段保留和必填事件字段。
- [ ] 运行 `python -m pytest tests/test_audit_redaction.py -v` 并确认因模块缺失失败。
- [ ] 实现不可变审计事件模型和递归脱敏函数。
- [ ] 重跑测试并确认通过。

### Task 2: SQLite 仓储与风险分析

**Files:**
- Create: `backend/audit/repository.py`
- Create: `backend/audit/risk.py`
- Test: `backend/tests/test_audit_repository.py`
- Test: `backend/tests/test_audit_risk.py`

**Interfaces:**
- Consumes: `AuditEvent`
- Produces: `AuditRepository.add_event`, `list_sessions`, `get_session`, `delete_session`
- Produces: `analyze_event(event: AuditEvent) -> list[RiskFinding]`

- [ ] 编写失败测试，覆盖事件排序、会话汇总、删除和危险命令规则。
- [ ] 运行两个测试文件并确认正确失败。
- [ ] 用标准库 `sqlite3` 实现仓储，用纯函数实现风险规则。
- [ ] 重跑测试并确认通过。

### Task 3: 审计服务与 HTTP API

**Files:**
- Create: `backend/services/audit_service.py`
- Modify: `backend/api/routes.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_audit_api.py`

**Interfaces:**
- Consumes: `AuditRepository`, `AuditEvent`, `analyze_event`
- Produces: `POST /api/audit/events`, `GET /api/audit/sessions`, `GET /api/audit/sessions/{id}`, `DELETE /api/audit/sessions/{id}`, `GET /api/audit/stream`

- [ ] 编写失败 API 测试，覆盖写入、查询、删除和非法 payload。
- [ ] 运行测试并确认端点不存在导致失败。
- [ ] 实现服务层、进程内订阅和薄路由。
- [ ] 重跑 API 与既有后端测试。

### Task 4: Codex 插件

**Files:**
- Create: `plugin/.codex-plugin/plugin.json`
- Create: `plugin/hooks/hooks.json`
- Create: `plugin/hooks/capture_event.py`
- Create: `plugin/README.md`
- Test: `backend/tests/test_hook_capture.py`

**Interfaces:**
- Consumes: Codex Hook stdin JSON
- Produces: HTTP POST to `/api/audit/events`

- [ ] 编写失败测试，验证脚本脱敏、请求格式和服务不可用时退出码为 0。
- [ ] 运行测试并确认脚本缺失导致失败。
- [ ] 实现零第三方依赖采集脚本与 Hook 配置。
- [ ] 验证插件 manifest 和 Hook 测试。

### Task 5: 前端数据层与审查工作台

**Files:**
- Replace: `src/app/page.tsx`
- Create: `src/app/lib/audit-types.ts`
- Create: `src/app/lib/audit-api.ts`
- Create: `src/app/components/SessionList.tsx`
- Create: `src/app/components/SessionSummary.tsx`
- Create: `src/app/components/AuditTimeline.tsx`
- Create: `src/app/components/EventInspector.tsx`
- Create: `src/app/components/ReviewComposer.tsx`
- Modify: `src/app/globals.css`
- Modify: `src/app/layout.tsx`

**Interfaces:**
- Consumes: 审计 REST API 与 SSE 事件流
- Produces: 三栏审查工作台和结构化修正提示

- [ ] 阅读 Next.js 16 的 Client Components、数据获取和错误处理文档。
- [ ] 定义与后端响应一致的 TypeScript 类型和 API 客户端。
- [ ] 将首页改为会话选择、时间线和事件详情状态容器。
- [ ] 实现响应式三栏界面、风险摘要和审查提示生成。
- [ ] 运行 `npm run lint` 和 `npm run build`，修复本任务引入的问题。

### Task 6: 品牌、文档与演示数据

**Files:**
- Modify: `README.md`
- Modify: `DESIGN.md`
- Modify: `package.json`
- Modify: `src/app/layout.tsx`
- Create: `docs/demo.md`
- Create: `backend/scripts/seed_demo.py`

**Interfaces:**
- Produces: EvolveTrace 品牌、安装步骤和无需真实 Codex 的演示流程

- [ ] 更新产品名、定位、架构、隐私边界和插件安装说明。
- [ ] 创建确定性的演示会话脚本与讲解文档。
- [ ] 扫描文档，移除与自研通用 Coding Agent 定位冲突的首页承诺。
- [ ] 运行演示脚本并确认会话可由 API 查询。

### Task 7: 全量验证

**Files:**
- Modify only files required to fix regressions introduced above.

**Interfaces:**
- Produces: 可安装、可运行、测试和构建通过的 EvolveTrace MVP

- [ ] 运行后端 `python -m pytest -v`。
- [ ] 运行前端 `npm run lint`。
- [ ] 运行前端 `npm run build`。
- [ ] 检查 `git diff --check` 和 `git status --short`。
- [ ] 人工核对验收标准并记录任何外部环境限制。

