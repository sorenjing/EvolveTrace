# EvolveLab

<p align="center">
  <strong>一个可视化、可定制的 AI Agent 实验平台</strong><br>
  看清 Agent 的每一步思考，给它装上你想要的任何工具
</p>

<p align="center">
  <img alt="License" src="https://img.shields.io/badge/license-PolyForm--Noncommercial-orange.svg">
  <img alt="Python" src="https://img.shields.io/badge/python-3.10+-3776AB.svg">
  <img alt="Next.js" src="https://img.shields.io/badge/Next.js-16-000000.svg">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.115-009688.svg">
  <img alt="PRs Welcome" src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg">
</p>

<p align="center">
  <a href="#这是什么">这是什么</a> ·
  <a href="#和-cursorcodexclaude-code-有什么不同">差异化</a> ·
  <a href="#能做什么">能做什么</a> ·
  <a href="#快速开始">快速开始</a> ·
  <a href="#架构">架构</a> ·
  <a href="#安全设计">安全设计</a>
</p>

---

## 这是什么？

EvolveLab 是一个**白盒的 AI Agent 实验平台**。

大多数 AI 工具（Cursor、Trae、Copilot）是**黑盒**——你输入需求，它给结果，中间过程你看不到。EvolveLab 反过来：Agent 的每一次思考、每一次工具调用、每一个观察结果，都实时展示在 Timeline 上，让你**看清 AI 是怎么想的**。

同时，EvolveLab 是**可定制的**——Agent 不只能用内置工具，还能自己创建新工具并持久化保存。你也可以手动给它加工具，把它改造成你专属的 Agent。

> 适合谁用？
> - 想学习 AI Agent 原理的开发者
> - 想调试 / 研究 Agent 行为的人
> - 想搭建个人自动化工作流的极客
> - 对"AI 能怎么思考"感到好奇的人

## 和 Cursor/Codex/Claude Code 有什么不同？

| 维度 | Cursor / Codex / Claude Code | EvolveLab |
|------|------------------------------|-----------|
| **过程可见性** | 黑盒，只给结果 | 白盒，每步思考可见 |
| **工具系统** | 固定内置 | 可动态创建/删除，Agent 能自举新工具 |
| **定位** | 代码助手（需求驱动） | Agent 实验平台（探索驱动） |
| **内核** | 闭源 | 自研 ReAct 内核，完全开源 |
| **数据** | 部分经过云端 | 完全本地运行 |

**一句话**：它们帮你写代码，EvolveLab 帮你理解 Agent 是怎么工作的。

## 能做什么

### 示例 1：让 Agent 分析你的项目

```
任务：分析这个项目的结构，找出主要模块

Agent 执行轨迹：
  Step 1  THOUGHT  我需要先看根目录有哪些文件
          ACTION   list_files(path=".")
          OBSERVE  backend/  src/  package.json  README.md ...

  Step 2  THOUGHT  有 backend 和 src，先看 backend 结构
          ACTION   list_files(path="backend")
          OBSERVE  agent/  api/  auth/  tools/  main.py ...

  Step 3  THOUGHT  读 main.py 了解入口
          ACTION   read_file(path="backend/main.py")
          OBSERVE  FastAPI 应用，注册了路由...

  ✅ 结果：这是一个前后端分离的 Agent 实验平台，后端 FastAPI
          提供 ReAct 内核和工具系统，前端 Next.js 做 Timeline 可视化...
```

### 示例 2：让 Agent 给自己加一个新工具

```
任务：我需要一个能把文本翻译成英文的工具，你创建一下

Agent 执行轨迹：
  Step 1  THOUGHT  现有工具没有翻译能力，我用 create_tool 创建
          ACTION   create_tool(
                     name="translate_to_en",
                     description="将中文文本翻译为英文",
                     args=["text"],
                     code="def run(**kwargs): ..."
                   )
          OBSERVE  [成功] 工具 'translate_to_en' 已创建并注册

  Step 2  THOUGHT  测试一下新工具
          ACTION   translate_to_en(text="你好世界")
          OBSERVE  Hello World

  ✅ 结果：已创建翻译工具，持久化保存，重启后仍可用
```

### 示例 3：让 Agent 修改代码并安全验证

```
任务：在 backend/tools 下加一个计算器工具

Agent 执行轨迹：
  Step 1  THOUGHT  修改项目源码前必须先创建快照
          ACTION   create_snapshot()
          OBSERVE  [成功] 快照 ID: a1b2c3d4

  Step 2  THOUGHT  写入计算器工具代码
          ACTION   write_file(path="backend/tools/custom/calc.py", content="...")
          OBSERVE  文件已写入

  Step 3  THOUGHT  验证修改没有破坏项目
          ACTION   verify_build()
          OBSERVE  [成功] 构建验证通过

  ✅ 结果：计算器工具已添加，构建验证通过
```

## 核心特性

- **白盒 Timeline** — 实时渲染 Agent 的 Thought → Action → Observation 闭环，每一步都看得见
- **自研 ReAct 内核** — 不依赖 LangChain/AutoGen，从零实现推理循环，强制结构化 JSON 输出，死循环检测 + 上下文压缩
- **可定制工具系统** — 16 个内置工具 + Agent 运行时自举新工具，持久化到本地，重启后自动加载
- **自我修改安全层** — Git 快照 → 修改 → 构建验证 → 失败自动回滚，让 Agent 改自己的代码也不会崩
- **多层安全沙箱** — 命令注入三层防御、路径越界防护、角色权限分级、管理接口认证
- **完全本地运行** — 代码不离开你的电脑，API Key 存浏览器 localStorage，不碰文件系统

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/sorenjing/EvolveLab.git
cd EvolveLab
```

### 2. 启动后端

```bash
cd backend
python -m venv venv

# Windows
.\venv\Scripts\pip install -r requirements.txt
.\venv\Scripts\uvicorn main:app --host 127.0.0.1 --port 8001 --reload

# Linux / macOS
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8001 --reload
```

### 3. 启动前端

```bash
# 回到项目根目录
npm install
npm run dev
```

浏览器访问 **http://localhost:3000**：

1. 点击右上角「设置」→ 填入 API Key → 测试连接 → 保存
2. 输入任务（如"分析这个项目的结构"）→ 点「执行」
3. 观察 Timeline 上 Agent 的实时思考过程

> **Windows 一键启动**：`.\start.ps1`

### 配置 API Key

API Key 在前端界面配置，保存在浏览器 localStorage，**不写入文件、不上传 GitHub**：

| 字段 | 说明 | 默认值 |
|------|------|--------|
| API Key | LLM API 密钥（必填） | — |
| Base URL | LLM API 地址 | `https://open.bigmodel.cn/api/paas/v4` |
| Model | 模型名称 | `glm-4-flash` |

<details>
<summary>支持的 LLM 提供商</summary>

| 提供商 | BASE_URL | 推荐 Model |
|--------|----------|-----------|
| 智谱 AI | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` |
| Moonshot | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` |

</details>

## 架构

```mermaid
graph TB
    subgraph Browser["Browser (Next.js 16)"]
        UI["任务输入 + Timeline 可视化<br/>配置面板 + 工具列表"]
    end

    subgraph Backend["Python FastAPI Backend"]
        Kernel["ReAct 内核<br/>Thought→Action→Observation"]
        Router["工具路由<br/>16 内置 + 动态自举"]
        Tools["工具实现<br/>File / Exec / Safety / Lifecycle"]
        Sandbox["安全沙箱<br/>权限 + 路径 + 命令防御"]
    end

    LLM["LLM API<br/>OpenAI-compatible"]

    UI -->|"POST /api/agent/stream (SSE)"| Kernel
    Kernel -->|"生成 Action"| Router
    Router --> Tools
    Tools --> Sandbox
    Sandbox -->|"Observation"| Kernel
    Kernel -->|"流式事件"| UI
    Kernel <-->|"推理"| LLM
```

## 技术栈

| 层级 | 选型 | 说明 |
|------|------|------|
| 前端 | Next.js 16 + React 19 + TypeScript | App Router, Tailwind CSS v4 |
| 后端 | Python 3.10+ + FastAPI + Uvicorn | SSE 流式推送 |
| LLM | OpenAI-compatible API | 默认智谱 GLM-4-Flash，可换任意兼容模型 |
| 通信 | SSE (Server-Sent Events) | 端到端流式 |

## 安全设计

Agent 能执行命令和修改文件，因此安全是第一优先级：

### 命令注入防御（三层）

1. **黑名单正则** — 拦截 `rm -rf`、`format`、`del /f` 等危险命令
2. **元字符禁用** — 禁止 `;` `&` `|` `` ` `` `$` `>` `<` 等 shell 元字符
3. **精确白名单** — `shlex` 解析后精确匹配白名单（`npm install` 放行，`npm; rm -rf` 拦截）

### 其他安全机制

- **路径沙箱** — 文件操作限制在项目目录内
- **写前备份** — 修改前自动创建 `.bak` 备份
- **角色权限** — 只读 / 标准 / 管理员三级权限
- **管理接口认证** — `/api/admin/*` 默认仅 localhost，远程需 `ADMIN_TOKEN`
- **速率限制** — 全局 30/min，Agent 接口 10/min，防止额度滥用
- **默认 localhost** — 服务默认监听 `127.0.0.1`，不暴露公网

### 自我修改安全层

Agent 修改自身源码时的保护流程：

| 阶段 | 操作 | 工具 |
|------|------|------|
| 修改前 | 创建 Git 快照 | `create_snapshot` |
| 修改 | 写入/编辑文件 | `write_file` / `edit_file` |
| 验证 | 后端语法 + 前端类型检查 | `verify_build` |
| 回滚 | 验证失败时恢复 | `rollback` |

## 演进路线

### 已完成

- [x] **基础 ReAct Loop** — Thought→Action→Observation 推理循环 + 工具系统 + 前端 Timeline
- [x] **安全加固** — 命令注入三层防御、会话 TTL、JSON 解析容错、速率限制、管理接口认证
- [x] **自我修改安全层** — Git 快照 + 构建验证 + 失败自动回滚
- [x] **Agent 自主扩展工具** — `create_tool` 动态注册 + 本地持久化 + 重启自动加载
- [x] **工程化优化** — LLM 指数退避重试、AST 代码安全审查、Redis 会话持久化（内存降级）、结构化日志、命令输出截断、Agent 接口 Token 鉴权、前端组件拆分、安全逻辑单元测试

### 近期规划（高价值 / 中等工作量）

#### ReAct 内核升级
- [ ] **反思（Reflection）机制** — 任务失败/步骤卡顿时自动回溯分析失败原因，调整策略重试；支持用户手动触发反思让 Agent 总结进度与问题
- [ ] **智能死循环检测升级** — 从「重复 Action 检测」升级为「进度停滞检测」，识别连续多步无实质产出，自动打断并提供「换策略 / 人工介入 / 终止」三选项

#### 产品体验打磨
- [ ] **Timeline 可视化增强** — 连续同类操作自动折叠分组、按「思考/行动/结果」筛选、步骤详情面板（完整 Prompt / 原始输出 / Token 消耗 / 耗时）、成功/失败/警告状态视觉化
- [ ] **任务模板首页** — 5-8 个高频任务模板（分析项目结构 / 代码审查 / 生成 README / 创建翻译工具 / 检查项目安全）一键执行
- [ ] **轨迹导出** — 支持将 Agent 执行轨迹导出为 JSON / Markdown，方便写报告与分享

#### 稳定性增强
- [ ] **LLM 调用熔断降级** — 连续失败自动熔断并友好提示，避免前端无响应
- [ ] **Token 消耗统计** — 前端实时展示当前任务/会话的 Token 消耗与预估费用

### 中期规划（架构级 / 较大工作量）

#### 分层记忆系统
- [ ] **短期记忆** — 当前会话完整步骤链，保留原始上下文
- [ ] **长期记忆** — 轻量向量库（Chroma / FAISS）存储工具使用历史、项目分析结论、通用知识，下次同类任务自动检索复用

#### 多 Agent 协作模式
- [ ] **规划-执行-审核三 Agent 分工** — 规划 Agent 拆解任务生成计划、执行 Agent 调用工具完成单步、审核 Agent 验证结果不合格打回重执行
- [ ] **Timeline 分层展示** — 支持切换查看单 Agent 视角或全局视角

#### 工具系统生态扩展
- [ ] **工具模板库** — 内置常用工具包（代码审查 / 接口文档生成 / 数据统计 / 简易爬虫）一键启用
- [ ] **第三方 API 一键接入** — 输入 OpenAI 格式 API 地址和描述，自动生成对应工具并注册
- [ ] **工具运行时隔离** — 自定义工具改用 Docker 容器 / 独立虚拟环境执行，支持 Node.js、Shell 多语言工具

#### 工程化升级
- [ ] **后端分层架构** — 抽离 Service / Repository 层，内核、工具、沙箱各自解耦
- [ ] **单元测试覆盖** — pytest 覆盖 ReAct 内核、安全沙箱、核心工具，核心模块覆盖率 ≥ 70%
- [ ] **轻量数据库接入** — SQLite 存储会话历史、工具元数据、执行日志，替代文件持久化
- [ ] **前端状态管理** — Zustand 统一管理会话/配置/工具状态，消除 any 类型
- [ ] **E2E 测试** — Playwright 覆盖核心流程（启动→配置 Key→执行任务→Timeline 渲染）

#### 沙箱体系升级
- [ ] **容器级运行沙箱** — 命令执行与文件修改放入 Docker 容器，从「规则防御」升级为「物理隔离」
- [ ] **细粒度权限控制** — 从三级角色细化到单工具权限，可配置每个工具的可读目录与可执行命令范围
- [ ] **Prompt 注入防护** — 输入输出敏感词检测，拦截读取 `.env`、绕过安全、破坏性操作指令

### 远期规划（生态与交付）

#### 部署与交付
- [ ] **Docker 一键部署** — 前后端 Dockerfile + docker-compose.yml，一条命令启动全套服务
- [ ] **启动脚本补全** — Linux/macOS `start.sh` + 启动前环境检查
- [ ] **GitHub Actions CI/CD** — PR 自动跑单测/格式检查/构建验证，主分支合并自动生成 Release

#### 前端交互完善
- [ ] **多会话管理** — 标签页式多会话，数据持久化到本地，不同任务并行不干扰
- [ ] **独立工具管理页** — 启用/禁用、在线编辑源码、手动测试、导出导入
- [ ] **时间轴回溯重跑** — 点击历史步骤回退到该节点，修改指令后从中间重新执行
- [ ] **基础体验补全** — 暗黑模式、响应式适配、全局错误边界

#### 开源生态
- [ ] **文档体系完善** — CONTRIBUTING.md / CHANGELOG.md / FAQ.md，双语 README
- [ ] **架构文档细化** — DESIGN.md 补充 ReAct 时序图、SSE 流程图、沙箱原理图（Mermaid）
- [ ] **入门教程** — docs/ 目录写 2-3 篇教程（搭建项目分析 Agent / 自定义工具开发指南）
- [ ] **社区友好配置** — Issue / PR 模板，README 徽章与简介优化

> 路线图按价值与工作量分阶段推进，优先做「高价值 + 中等工作量」的项。欢迎在 Issue 中讨论优先级或认领任务。

## 面试要点（给求职者）

如果你把 EvolveLab 放在简历上，以下是面试官大概率会问的问题和回答要点：

### 1. 为什么不用 LangChain，而是自己实现 ReAct 循环？

**核心回答**：为了深入理解 Agent 底层机制和获得完全控制权。

- LangChain 把 ReAct 循环、Prompt 模板、工具路由全部封装成黑盒，调用者只需配置参数
- 自研让我掌握了 Agent 的完整工作流：Prompt 构造 → JSON 强制输出 → 工具路由 → 错误处理 → 死循环检测 → 上下文压缩
- 实际代码量不大（kernel.py ~130 行），但每一行都理解为什么这么写
- 比 LangChain 更轻量：仅依赖 httpx（vs LangChain 的 5+ 个包）

**如果面试官追问"那你懂 LangChain 吗"**：

> "我研究过 LangChain 的 Agent 模块。我自研的每一层都对应 LangChain 的一个概念：AgentKernel.run() 对应 AgentExecutor，TOOLS dict 对应 BaseTool，self.history 对应 ConversationBufferMemory，build_system_prompt() 对应 PromptTemplate。因为底层原理已经吃透了，如果需要用 LangChain，我能很快上手。"

**简历上可以这样写**：`LangChain（了解 Agent/Tool/Chain 模块，基于自研 ReAct 实践验证）`

### 2. ReAct 循环是怎么实现的？

**核心回答**：while 循环 + JSON 强制输出 + 工具路由 + 死循环检测。

```
while step < max_steps:
    1. 拼 System Prompt + 历史 Thought/Action/Observation
    2. 调 LLM，要求输出 JSON {thought, action, actionInput}
    3. 解析 JSON（失败则正则提取 + 容错 fallback）
    4. action == "final_answer" → 结束
    5. 从 TOOLS dict 查找工具函数，执行得到 Observation
    6. 追加到 history，继续循环
    7. 检测：连续 3 次相同 action+observation → 强制终止
```

### 3. 安全设计是怎么做的？

**三层命令注入防御**：
1. 黑名单正则：拦截 `rm -rf /`、`fork bomb` 等
2. 元字符禁用：禁止 `;` `|` `&` `` ` `` `$` `>` `<` 等 shell 连接符
3. shlex 白名单精确匹配：用 `shlex.split` 解析后精确匹配白名单，而非 startswith

**路径沙箱**：所有文件操作必须 `resolve()` 后在 `PROJECT_ROOT` 内

**自我修改安全层**：Git 快照 → 修改代码 → 构建验证 → 失败自动回滚

### 4. 工具自举（Agent 给自己创建新工具）是怎么实现的？

1. `create_tool` 接收工具名、描述、参数、Python 代码
2. AST 安全审查：扫描 `eval`/`exec`/`os.system`/`subprocess` 等危险调用
3. 审查通过后写入 `tools/custom/{name}.py`
4. 用 `importlib` 动态 import，注册到 `TOOLS` dict
5. 下次启动时 `registry.load_all_custom_tools()` 自动扫描加载

### 5. SSE vs WebSocket 为什么选 SSE？

- SSE 是单向推送（服务端→客户端），Agent 执行轨迹天然是单向的
- SSE 基于 HTTP，天然支持代理、CDN、断线重连
- 实现简单：不需要 WebSocket 的握手、心跳、帧协议
- 用 `fetch` + `ReadableStream` 消费，前端代码更简洁

### 6. 上下文压缩是怎么做的？

- 步数超过阈值（8 步）时触发压缩
- 保留最近 4 步原始细节，之前的步骤压缩为摘要
- 关键约束：**绝不丢失 todo 和任务完成状态**
- 每步按工具类型做结构化摘要（文件操作省略内容，命令操作保留输出摘要）

### 7. 还有哪些技术亮点？

- **LLM 指数退避重试**：5xx/网络错误自动重试 2 次（1s/2s）
- **JSON 解析容错**：栈匹配 `{}` 处理嵌套 JSON，失败则 fallback
- **会话持久化**：Redis 优先 + 内存降级（REDIS_URL 未配置时自动用内存）
- **速率限制**：全局 30/min + Agent 10/min，防 LLM 额度滥用
- **API Key 存前端 localStorage**：不写后端文件，避免 `.env` 泄露

## 贡献

欢迎 Issue 和 PR！详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

提 PR 前请确保：

1. 后端代码通过 `python -m py_compile` 语法检查
2. 前端代码通过 `npm run build` 构建检查
3. 不要提交 `.env` 等含敏感信息的文件

## License

本项目采用 [PolyForm Noncommercial License 1.0.0](LICENSE)。

- ✅ **允许**：个人学习、研究、教学、内部非商用使用、修改与再分发（须保留本许可）
- ❌ **禁止**：未经授权的商用——包括但不限于销售本软件、嵌入付费产品/付费服务、作为 SaaS 提供、用于支撑付费业务的内部使用

如需商用，请通过 GitHub Issues 联系作者获取商业授权。

> 个人项目，独立维护，感谢理解与支持。
