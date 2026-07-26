# EvolveLab — 设计方案

> 面向 Coding Agent 可观测性、工具扩展与安全边界的研究型源码项目

## 1. 技术选型

| 层级 | 选型 | 理由 |
|------|------|------|
| 前端 | Next.js 16 (App Router) + TypeScript + Tailwind CSS | Timeline 可视化、配置面板、工具管理 |
| 后端 | Python + FastAPI + Uvicorn | SSE 流式响应、工具执行（Python 生态适合文件/系统操作） |
| 大模型 | OpenAI-compatible API（智谱 GLM 等） | 前端配置 API Key，经后端转发调用 |
| 通信 | SSE (Server-Sent Events) | 实时推送 Agent 执行轨迹 |

> **架构说明**：前后端分离。前端为 Next.js 静态页面，后端为独立 Python FastAPI 服务。
> Agent 内核、工具系统、安全层均在后端 Python 实现。

---

## 2. Agent 内核设计

### 2.1 核心抽象

```
┌─────────────────────────────────────────────────────────────┐
│                        Agent Kernel                          │
│  ┌─────────────┐   ┌─────────────┐   ┌──────────────────┐  │
│  │  ReAct Loop │ → │ Tool Router │ → │ Executor (Sandbox)│  │
│  └─────────────┘   └─────────────┘   └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

#### ReAct 推理循环（自研，不依赖 LangChain）

```
while (step < maxSteps && !taskDone):
    1. 构造 Prompt：System Prompt + 历史 Thought/Action/Observation + 当前任务
    2. 调用 LLM，要求输出 JSON：{ thought, action, actionInput }
    3. 解析 JSON（失败则容错重试）
    4. 若 action === "final_answer" → 结束循环
    5. 否则，路由到对应 Tool，执行得到 Observation
    6. 将 Thought/Action/Observation 写入历史，继续循环
```

### 2.2 为什么不用 LangChain（与 LangChain 概念映射）

> 面试时最常被问的问题。以下是刻意选择自研的核心理由，以及与 LangChain 概念的对应关系。

| 自研（EvolveLab） | LangChain 等价概念 | 选择自研的理由 |
|---|---|---|
| `AgentKernel.run()` | `AgentExecutor` | 完全控制循环逻辑，能在任意节点插入安全检测、上下文压缩 |
| `TOOLS` dict + `TOOLS_META` | `BaseTool` / `@tool` | 更轻量，无需继承框架基类，普通函数即工具 |
| `self.history` (list[dict]) | `ConversationBufferMemory` | 自定义压缩策略（保留 todo + 完成状态），LangChain 的 memory 做不到 |
| `AgentEvent` (dataclass) | `AgentAction` / `AgentFinish` | 更细粒度的事件（thought/action/observation/error/complete），方便 SSE 流式推送 |
| `LLMClient.chat()` | `ChatOpenAI` | 直接 httpx 调用，无框架抽象层，指数退避重试、JSON 容错全自控 |
| `build_system_prompt()` | `PromptTemplate` | 动态拼接工具元数据，按视觉能力决定是否暴露截图工具 |

**选择自研的本质原因**：
1. Agent 循环的核心逻辑不到 200 行（kernel.py + llm.py + prompts.py），不值得引入一个框架
2. 安全需求（命令注入三层防御、路径沙箱、Git 快照回滚）必须嵌入循环内部，框架的抽象层反而成为障碍
3. 面试时能讲清楚每一行代码为什么这么写，比"我调了 LangChain 的 AgentExecutor"有说服力得多

> 如果你需要证明自己**也懂 LangChain**：这个项目的每一层都对应 LangChain 的一个模块，你只需要在面试时把这个映射表讲出来即可。

### 2.3 工具层设计

| 工具 | 功能 | 安全边界 |
|------|------|----------|
| `read_file` | 读取文件内容 | 项目目录内，<1MB |
| `write_file` | 写入/覆盖文件 | 项目目录内，写前备份 |
| `edit_file` | Search/Replace 修改文件 | 同上 |
| `delete_file` | 删除文件 | 需高权限 |
| `execute_command` | 执行命令 | 三层命令注入防御 + 白名单 |
| `list_files` | 列出目录 | 项目目录内 |
| `search_files` | 搜索文件内容/文件名 | 项目目录内 |
| `screenshot` | 截屏 | — |
| `cleanup` | 清理临时文件 | — |
| `create_snapshot` | 创建 Git 快照 | 自我修改安全层 |
| `verify_build` | 构建验证 | 后端语法 + 前端类型检查 |
| `rollback` | 回滚到快照 | 验证失败时调用 |
| `create_tool` | 创建自定义工具 | Phase 3：Agent 自主扩展能力 |
| `list_tools` | 列出所有工具 | 查看能力边界 |
| `delete_tool` | 删除自定义工具 | 仅限自定义工具 |
| `final_answer` | 结束任务 | — |

### 2.4 容错与防死循环

- **JSON 解析容错**：LLM 返回非 JSON 时，正则提取 + 重试
- **死循环检测**：连续 3 次相同 action 强制终止（按 action + observation 完全匹配）
- **上下文压缩**：历史过长时自动压缩，保留 todo 和完成状态
- **工具执行报错**：错误信息作为 Observation 返回，让 LLM 自行决策

### 2.5 任务进度跟踪（todo 结构化）

为防止长任务在上下文压缩后丢失进度，系统约定 LLM 在每步输出中携带 `todos` 字段：

```json
{
  "thought": "...",
  "action": "...",
  "actionInput": { ... },
  "todos": [
    {"content": "读取文件", "done": true},
    {"content": "修改代码", "done": false}
  ]
}
```

**提取策略**（`context.py: extract_todos()`）：
1. 优先从 `actionInput.todos` 结构化字段提取（新约定）
2. 文本匹配兜底：从 thought/observation 中提取 `[x]`/`[ ]`/`已完成：`/`TODO:` 标记行
3. 按 content 去重，同 todo 后出现覆盖前者状态

**system prompt 约束**：`prompts.py: build_system_prompt()` 要求模型在可拆分任务中输出 `todos` 字段，简单单步任务可省略。

### 2.6 LLM 调用与流式输出

| 方法 | 用途 | 特点 |
|------|------|------|
| `LLMClient.chat()` | Agent 内核调用（需要完整 JSON） | 非流式，自动重试，返回解析后的 dict |
| `LLMClient.chat_stream()` | 前端打字效果 | 流式 SSE，逐 token yield，不自动重试 |

- `max_tokens` 参数化（默认 4096，旧值 2048 已废弃）
- 连接超时 10s + 读取超时 120s 分离
- 5xx + 网络异常自动重试（指数退避，最多 2 次），4xx 不重试

### 2.7 视觉能力检测

`auth/capability.py` 维护已知视觉模型白名单：

```python
KNOWN_VISION_MODELS = {
    "gpt-4o", "gpt-4-turbo", "gpt-4-vision",
    "claude-3", "claude-3.5",
    "gemini-1.5", "gemini-pro-vision",
    "qwen-vl", "qwen2-vl",
    "glm-4v",          # 智谱 GLM-4V（视觉版）
    "glm-4-plus-v",
}
```

**设计原则**：必须是视觉版本的精确标识，避免子串误匹配。例如 `glm-4-flash` 不是视觉模型（`glm-4v` 才是），已从白名单移除。

---

## 3. 安全设计

### 3.1 命令注入防御（三层）

1. **黑名单正则**：拦截 `rm -rf /`、`format`、`del /f` 等危险命令
2. **元字符禁用**：禁止 `;`、`|`、`&`、`$()`、反引号等 shell 元字符
3. **shlex 精确白名单匹配**：用 `shlex.split` 解析后，精确匹配白名单命令前缀

### 3.2 管理接口认证

- `/api/admin/*` 接口默认仅允许 localhost 访问
- 非 localhost 访问需配置 `ADMIN_TOKEN` 环境变量并携带 `X-Admin-Token` 请求头

### 3.3 网络安全

- **CORS**：默认仅允许 `http://localhost:3000`，可通过 `ALLOWED_ORIGINS` 环境变量配置
- **监听地址**：默认 `127.0.0.1`，需外网访问时设置 `HOST=0.0.0.0`
- **速率限制**：全局 30 次/分钟，Agent 接口 10 次/分钟（防止 LLM 额度滥用）

### 3.4 自我修改安全层

| 阶段 | 操作 | 工具 |
|------|------|------|
| 修改前 | 创建 Git 快照（HEAD + stash + untracked） | `create_snapshot` |
| 修改 | 写入/编辑文件 | `write_file` / `edit_file` |
| 验证 | 后端语法检查 + 前端类型检查 | `verify_build` |
| 回滚 | 验证失败时恢复 | `rollback` |

---

## 4. 自我进化机制

### 4.1 进化层级

| 层级 | 修改对象 | 实现状态 |
|------|----------|----------|
| L1 新增工具 | `backend/tools/custom/` 下新增工具文件 | ✅ Phase 3 已实现 |
| L2 修改 Prompt | `backend/agent/prompts.py` | ⬜ Phase 4 |
| L3 修改内核 | `backend/agent/kernel.py` | ⬜ Phase 4 |
| L4 修改配置 | 依赖列表、构建配置 | ⬜ Phase 4 |

### 4.2 工具自举流程（L1 已实现）

用户任务："给自己增加一个能调用 HTTP API 的工具"

```
Step 1: list_tools() → 查看当前能力边界
Step 2: create_tool(name="http_get", description="HTTP GET 请求", args=["url"], code="...")
         → 写入 custom/http_get.py + 动态加载注册
Step 3: http_get(url="https://api.example.com/data") → 调用新工具
Step 4: final_answer(result="已创建 http_get 工具并完成任务")
```

工具持久化到 `backend/tools/custom/` 目录，重启后自动加载。

---

## 5. 系统架构图

```
┌──────────────────────────────────────────────────────────────┐
│                        Browser                               │
│  ┌──────────────┐    ┌──────────────────────────────────┐  │
│  │  Task Input  │───→│  Timeline (SSE Stream Renderer)  │  │
│  │  Config Panel│    │  Tools Panel                     │  │
│  └──────────────┘    └──────────────────────────────────┘  │
└────────────────────────────┬─────────────────────────────────┘
                             │ POST /api/agent/stream (SSE)
┌────────────────────────────▼─────────────────────────────────┐
│                  Python FastAPI Backend                       │
│  ┌──────────────┐    ┌──────────────┐    ┌─────────────┐   │
│  │ Agent Kernel │───→│  Tool Router │───→│  Tool Impl  │   │
│  │ (ReAct Loop) │    │              │    │ (File/Exec) │   │
│  └──────────────┘    └──────────────┘    └─────────────┘   │
│         ↑              ┌──────────────┐                     │
│         └──────────────│ Safety Layer │                     │
│                        │ (Snapshot/   │                     │
│                        │  Verify/     │                     │
│                        │  Rollback)   │                     │
│                        └──────────────┘                     │
│         ↑                                                   │
│         └────────── LLM API ────────────────                │
│                     (OpenAI-compatible)                      │
└──────────────────────────────────────────────────────────────┘
```

---

## 6. 分层架构

后端采用经典的**路由层 / 服务层 / 仓储层**三层分离，路由层保持薄（仅 HTTP 转换），业务逻辑下沉到 Service：

```
┌─────────────────────────────────────────────────────────────┐
│  api/routes.py    （薄路由层：HTTP 解析、参数校验、鉴权依赖）│
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  services/         （服务层：业务编排，不感知 HTTP 细节）    │
│  ├── agent_service.py   Agent 创建 + SSE 事件流 + 会话查询  │
│  ├── tool_service.py    工具列表 + 删除                     │
│  ├── admin_service.py   角色/白名单/能力/清理               │
│  └── config_service.py  LLM 配置测试                        │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  仓储与基础设施层                                            │
│  ├── session_store.py   会话存储抽象（内存 / Redis）        │
│  ├── agent/kernel.py    Agent 内核（ReAct 循环）            │
│  ├── tools/             工具注册表与实现                    │
│  └── auth/              权限/能力/管理认证                  │
└─────────────────────────────────────────────────────────────┘

异常处理：services 抛 AppError 子类，由 exceptions.py 的全局处理器
统一为 {code, message} 错误响应；成功响应保持原格式不破坏前端。
```

设计原则：
- 路由层不写业务逻辑，service 不感知 HTTP（便于复用与测试）
- 成功响应保持原格式（前端无需改造），仅统一错误响应
- 仓储层已用 repository 模式（session_store），不额外抽象避免过度设计

---

## 7. 目录结构

```
EvolveLab/
├── backend/
│   ├── main.py                   # FastAPI 入口（注册路由、异常、中间件）
│   ├── config.py                 # 配置（环境变量）
│   ├── exceptions.py             # 自定义异常 + 全局异常处理器
│   ├── session_store.py          # 会话存储抽象（内存 / Redis）
│   ├── logger.py                 # 结构化日志
│   ├── agent/
│   │   ├── kernel.py             # Agent Kernel（ReAct 循环）
│   │   ├── llm.py                # LLM 调用封装
│   │   └── prompts.py            # System Prompt 模板
│   ├── api/
│   │   └── routes.py             # 薄路由层（仅 HTTP 转换 + 鉴权依赖）
│   ├── services/                 # 业务服务层
│   │   ├── agent_service.py      # Agent 运行 + SSE 流 + 会话
│   │   ├── tool_service.py       # 工具列表与删除
│   │   ├── admin_service.py      # 角色/白名单/能力/清理
│   │   └── config_service.py     # LLM 配置测试
│   ├── auth/
│   │   ├── permissions.py        # 权限管理 + 命令注入防御
│   │   ├── capability.py         # LLM 能力探测
│   │   └── admin.py              # 管理接口认证
│   ├── tools/
│   │   ├── __init__.py           # 工具注册表
│   │   ├── file_tools.py         # 文件操作工具
│   │   ├── system_tools.py       # 系统命令工具
│   │   ├── screenshot.py         # 截屏工具
│   │   ├── cleanup.py            # 清理工具
│   │   ├── safety.py             # 自我修改安全层
│   │   ├── lifecycle.py          # 工具生命周期管理
│   │   ├── registry.py           # 自定义工具动态加载器
│   │   └── custom/               # Agent 创建的自定义工具（持久化）
│   ├── tests/
│   │   └── test_code_safety.py   # 代码安全测试
│   ├── requirements.txt          # 依赖锁定
│   ├── pyproject.toml            # black/isort/pytest 配置
│   └── Dockerfile
├── src/
│   └── app/
│       ├── layout.tsx           # 根布局（主题脚本 + ErrorBoundary）
│       ├── page.tsx             # 主页（状态管理 + SSE 消费）
│       ├── globals.css          # Tailwind + class-based dark 变体
│       ├── components/
│       │   ├── Header.tsx       # 顶栏（含 ThemeToggle）
│       │   ├── InputArea.tsx    # 任务输入
│       │   ├── Timeline.tsx      # 执行轨迹（状态色/折叠/长内容）
│       │   ├── ConfigPanel.tsx  # LLM 配置面板
│       │   ├── ToolsPanel.tsx   # 工具管理面板
│       │   ├── TaskTemplates.tsx # 任务模板首页
│       │   ├── ThemeToggle.tsx  # 暗黑模式切换
│       │   └── ErrorBoundary.tsx # 全局错误边界
│       └── lib/
│           ├── types.ts         # 共享类型与配置工具
│           └── templates.ts     # 任务模板数据
├── docs/
│   └── usage.md                 # 使用文档
├── .github/workflows/ci.yml     # GitHub Actions CI
├── docker-compose.yml           # Docker 一键部署
├── Dockerfile                   # 前端镜像
├── README.md
├── DESIGN.md                    # 本文档
├── RUN.md                       # 运行与部署指南
└── package.json
```

---

## 8. 演进路线

- [x] **Phase 1**：基础 ReAct Loop + 工具系统 + 前端 Timeline
- [x] **安全加固**：命令注入防御、会话 TTL、JSON 解析容错、单例修复
- [x] **Phase 2**：自我修改安全层（Git 快照 + 构建验证 + 回滚）
- [x] **Phase 3**：Agent 自主扩展工具（create_tool + 本地持久化 + 工具列表）
- [ ] **Phase 4**：L2/L3 Prompt/内核修改
