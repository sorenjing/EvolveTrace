const project = {
  "id": "evolvetrace",
  "title": "EvolveTrace",
  "theme": "evidence",
  "mark": "ET",
  "repository": "https://github.com/sorenjing/EvolveTrace",
  "license": "Apache-2.0",
  "eyebrow": "CODING AGENT · EVIDENCE & REVIEW",
  "headline": "看清 Agent 的执行，<br><strong>再决定是否接受。</strong>",
  "description": "把任务契约、项目上下文、执行事件、验证结果与人工复核放进同一条证据链。EvolveTrace 在你的电脑上运行，保留每一次判断的依据。",
  "footer": "本地保存执行证据，保留人的最终判断。",
  "startTitle": "下载、准备环境，然后本地启动。",
  "startDescription": "首次安装需要 Python、Node.js 和 PowerShell。完成依赖安装与工作台构建后，用一个命令启动本地服务。",
  "commandCaption": "完成首次安装之后",
  "downloadDescription": "获取明确提交版本的源码。当前提供源码快照，需要按文档安装依赖后运行。",
  "requirements": "准备 Python 3.11 或更新版本、Node.js 22 或更新版本以及 PowerShell。首次安装需要联网下载依赖；日常执行证据保存在本地。",
  "features": [
    {
      "title": "把事件还原成执行证据",
      "text": "Codex Hooks 采集可观察事件，经过脱敏、去重写入 SQLite；时间线展示工具调用、修改范围和失败信息。"
    },
    {
      "title": "用验收条件核对结果",
      "text": "Task Contract 绑定上下文与 Run。已有确定性评估覆盖上下文 freshness、仓库范围和验证证据。"
    },
    {
      "title": "由人复核，再比较修正",
      "text": "逐项查看评估依据，记录 accepted 或 needs_fix。修正后的 Run 可以与此前结果对比，保留复核记录。"
    }
  ],
  "available": "Codex 事件采集、脱敏与本地存储、Task / Context / Run 绑定、确定性评估、人工复核，以及修正前后的 Run 对比。",
  "planned": "更多评估器、通用 Regression Case 导入导出与重放，以及经过单独设计的可选 LLM Judge。",
  "companion": {
    "title": "AI Context Kit",
    "repository": "https://github.com/sorenjing/ai-context-kit",
    "text": "AI Context Kit 准备可追踪的项目上下文和任务契约；EvolveTrace 接收版本化的 JSON 交接，记录随后发生的执行与复核。"
  },
  "diagram": "<div class=\"diagram\" aria-label=\"任务证据链示意\"><div class=\"diagram-label\"><span>RUN / EVIDENCE</span><span>工作流示意</span></div><p class=\"diagram-title\">一次任务，五个可核对的环节</p><div class=\"evidence-row\"><span class=\"step-number\">01</span><div>Task Contract<small>目标 · 范围 · 验收条件</small></div><span class=\"state\">契约</span></div><div class=\"evidence-row\"><span class=\"step-number\">02</span><div>Context Snapshot<small>来源版本 · freshness</small></div><span class=\"state\">上下文</span></div><div class=\"evidence-row\"><span class=\"step-number\">03</span><div>Observable Events<small>工具输入输出 · 修改 · 风险</small></div><span class=\"state\">证据</span></div><div class=\"evidence-row\"><span class=\"step-number\">04</span><div>Deterministic Evals<small>逐项结果 · evidence refs</small></div><span class=\"state\">评估</span></div><div class=\"evidence-row\"><span class=\"step-number\">05</span><div>Human Review<small>接受 · 修正 · 对比</small></div><span class=\"state\">复核</span></div></div>",
  "quickStart": "# 在本机运行 EvolveTrace\n\n## 1. 下载并解压\n\n从[下载页](download.html)获取源码 ZIP，解压后在仓库根目录打开 PowerShell。建议使用 Python 3.11+、Node.js 22+。需要安装 Codex Hook 时，使用支持本地插件的客户端。\n\n## 2. 准备后端环境\n\n```powershell\ncd backend\npython -m venv venv\nvenv\\Scripts\\python.exe -m pip install -r requirements-dev.txt\ncd ..\n```\n\n## 3. 构建工作台\n\n```powershell\n./scripts/build_static_ui.ps1\n```\n\n该步骤安装前端依赖并生成由后端提供的静态工作台。\n\n## 4. 启动本地服务\n\n```powershell\n./start.ps1\n```\n\n打开 `http://127.0.0.1:8001`。在 Codex 内置浏览器中使用时，运行 `./start.ps1 -NoBrowser`，再打开同一地址。\n\n## 5. 接入真实执行\n\n按[使用手册](docs/usage.html)安装并启用 `plugin/` 中的本地 Codex Hook，然后确认事件进入工作台。遇到没有事件、任务未绑定或验证证据缺失时，查看[观测与排障](docs/observability.html)。\n\n## 与 AI Context Kit 配合\n\n```powershell\naictx task prepare <项目名> --intent \"本次任务目标\" --platform codex\naictx task submit <task-id> --evolvetrace-url http://127.0.0.1:8001\n```\n\n## 运行边界\n\n这个官网提供介绍、文档和下载，不会连接你本地的 Hook、工作区或数据库。实际审查服务默认只监听本机；普通事件采集失败不会补发，缺失事件不能证明某个动作没有发生。",
  "documents": [
    {
      "source": "README.md",
      "slug": "overview",
      "title": "项目概览",
      "group": "OVERVIEW",
      "description": "用途、已实现能力和下一阶段计划。"
    },
    {
      "source": "RUN.md",
      "slug": "run",
      "title": "运行与部署",
      "group": "INSTALL",
      "description": "单进程运行、本地开发与 Docker 配置。"
    },
    {
      "source": "docs/usage.md",
      "slug": "usage",
      "title": "中文使用手册",
      "group": "WORKFLOW",
      "description": "从安装和 Hook 接入，到任务审查与修正对比。"
    },
    {
      "source": "docs/observability.md",
      "slug": "observability",
      "title": "观测与排障",
      "group": "DIAGNOSE",
      "description": "逐层检查服务、事件、Run 和 Evaluation。"
    },
    {
      "source": "docs/context-evidence-demo.md",
      "slug": "context-evidence",
      "title": "上下文证据演示",
      "group": "INTEGRATION",
      "description": "了解 Context Receipt 与任务证据链的演示流程。"
    },
    {
      "source": "docs/hook-event-contract.md",
      "slug": "hook-events",
      "title": "Hook 事件契约",
      "group": "REFERENCE",
      "description": "事件协议与适配器边界，供集成开发参考。"
    }
  ]
}

export default project
