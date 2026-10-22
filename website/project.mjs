const project = {
  "id": "evolvetrace",
  "title": "EvolveTrace",
  "theme": "evidence",
  "mark": "ET",
  "repository": "https://github.com/sorenjing/EvolveTrace",
  "license": "Apache-2.0 · Context: MIT",
  "eyebrow": "CODING AGENT · LOCAL COMMAND AUDIT",
  "headline": "Agent 反复执行了什么？<br><strong>从记录中找到线索。</strong>",
  "description": "先查看需要核对的线索，再按操作目的查看次数、结果与耗时覆盖。追溯重复操作和连续失败，定位到具体执行证据；需要验收时，再关联上下文、任务与验证条件。执行记录保存在本机，无需模型账号。",
  "footer": "本地保存执行证据，保留人的最终判断。",
  "startTitle": "下载、准备环境，然后本地启动。",
  "startDescription": "首次安装需要 Python、Node.js 和 PowerShell。完成依赖安装与工作台构建后，用一个命令启动本地服务。",
  "commandCaption": "完成首次安装之后",
  "downloadDescription": "获取明确提交版本的源码。当前提供源码快照，需要按文档安装依赖后运行。",
  "requirements": "准备 Python 3.11 或更新版本、Node.js 22 或更新版本以及 PowerShell。首次安装需要联网下载依赖；日常执行证据保存在本地。",
  "features": [
    {
      "title": "按项目看清命令与重复操作",
      "text": "区分定位文件、搜索内容、阅读、修改、测试、构建与版本操作，逐类展示结果和耗时样本。正常查询的无匹配或差异单列；推断与未知明确标注，提醒可定位具体证据。"
    },
    {
      "title": "用验收条件核对结果",
      "text": "通过 CLI / API 准备 Task 与上下文，在工作台查看 Run 并运行确定性评估。未接入的必需验收条件会阻止接受，不默认通过。"
    },
    {
      "title": "让经验经过人工确认",
      "text": "从分析窗口复制带证据的提示给 Codex，人工确认后保存审计记忆，由 Context 按项目回读。工作台显示客户端已上报的返回时间与记忆；输出声明不代表模型采用。"
    }
  ],
  "available": "早期版本：工作台提供命令审计、证据补齐状态、历史恢复、人工确认记忆，以及已结束 Run 的评估与人工复核。需修复后可准备新尝试，并对比已复核的前后 Run；执行修正仍需在新 Codex 会话完成。本地 Run 支持回归草稿导出、人工冻结和离线证据重新评分。Task / Context 初次创建通过 CLI / API 提供。命令频次不测量真实磁盘 I/O，不能诊断硬件损坏；分析提示由用户自行发送给 Codex。",
  "planned": "优先用真实任务验证发现问题、记录处理、新 Run 与同条件复核的操作路径，再扩展更多评估器和通用回归案例。可选 LLM Judge、系统资源采集与 Codex 原生分析弹窗尚未接入。",
  "companion": {
    "title": "EvolveTrace Context",
    "repository": "https://github.com/sorenjing/EvolveTrace/tree/master/context",
    "text": "EvolveTrace Context 准备可追踪的项目上下文和任务契约；执行审查组件接收版本化的 JSON 交接，记录随后发生的执行与复核。两者在同一仓库维护。"
  },
  "diagram": "<div class=\"diagram\" aria-label=\"任务证据链示意\"><div class=\"diagram-label\"><span>RUN / EVIDENCE</span><span>工作流示意</span></div><p class=\"diagram-title\">一次任务，五个可核对的环节</p><div class=\"evidence-row\"><span class=\"step-number\">01</span><div>Task Contract<small>目标 · 范围 · 验收条件</small></div><span class=\"state\">契约</span></div><div class=\"evidence-row\"><span class=\"step-number\">02</span><div>Context Snapshot<small>来源版本 · freshness</small></div><span class=\"state\">上下文</span></div><div class=\"evidence-row\"><span class=\"step-number\">03</span><div>Observable Events<small>工具输入输出 · 修改 · 风险</small></div><span class=\"state\">证据</span></div><div class=\"evidence-row\"><span class=\"step-number\">04</span><div>Deterministic Evals<small>逐项结果 · evidence refs</small></div><span class=\"state\">评估</span></div><div class=\"evidence-row\"><span class=\"step-number\">05</span><div>Human Review<small>接受 · 修正 · 对比</small></div><span class=\"state\">复核</span></div></div>",
  "quickStart": "# 在本机运行 EvolveTrace\n\n## 1. 下载并解压\n\n从[下载页](download.html)获取源码 ZIP，解压后在仓库根目录打开 PowerShell。建议使用 Python 3.11+、Node.js 22+。需要安装 Codex Hook 时，使用支持本地插件的客户端。\n\n## 2. 准备后端环境\n\n```powershell\ncd backend\npython -m venv venv\nvenv\\Scripts\\python.exe -m pip install --upgrade pip\nvenv\\Scripts\\python.exe -m pip install -r requirements-dev.txt\ncd ..\n```\n\n## 3. 构建工作台\n\n```powershell\n./scripts/build_static_ui.ps1\n```\n\n该步骤安装前端依赖并生成由后端提供的静态工作台。\n\n## 4. 启动本地服务\n\n```powershell\n./start.ps1\n```\n\n打开 `http://127.0.0.1:8001`。在 Codex 内置浏览器中使用时，运行 `./start.ps1 -NoBrowser`，再打开同一地址。\n\n## 5. 接入真实执行\n\n按[使用手册](docs/usage.html)安装并启用仓库根目录的统一 EvolveTrace 插件（见[合并使用指南](docs/consolidation.html)），然后确认事件进入工作台。遇到没有事件、任务未绑定或验证证据缺失时，查看[观测与排障](docs/observability.html)。\n\n## 使用 EvolveTrace Context\n\n先在仓库根目录安装上下文 CLI：\n\n```powershell\npython -m pip install ./context\n\naictx task prepare <项目名> --intent \"本次任务目标\" --platform codex\naictx task submit <task-id> --evolvetrace-url http://127.0.0.1:8001\n```\n\n## 跨项目命令审计\n\n在已配置 `.aictx.toml` 的工作区运行 `aictx audit sync` 登记项目，再用 `aictx audit report` 查看统计。也可运行 `./start.ps1 -NoBrowser -Detached` 保持后台服务。完整流程见[跨项目审计与记忆](docs/workspace-audit.html)。\n\n## 运行边界\n\n这个官网提供介绍、文档和下载，不会连接你本地的 Hook、工作区或数据库。实际审查服务默认只监听本机；普通事件采集失败不会补发，缺失事件不能证明某个动作没有发生。",
  "documents": [
    {
      "source": "docs/demo.md",
      "slug": "demo",
      "title": "先用合成数据体验",
      "group": "WORKFLOW",
      "description": "独立端口与演示数据库，无需接入真实项目，查看 Task、Run 和执行时间线。"
    },
    {
      "source": "docs/workspace-audit.md",
      "slug": "workspace-audit",
      "title": "跨项目命令审计与记忆",
      "group": "WORKFLOW",
      "description": "项目登记、命令统计、证据来源、选择分析和人工确认记忆。"
    },
    {
      "source": "docs/context-design.md",
      "slug": "context-design",
      "title": "Context 设计与学习路径",
      "group": "INTEGRATION",
      "description": "受控上下文输入、交付证据与任务运行绑定的代码阅读及验证路径。"
    },
    {
      "source": "docs/consolidation.md",
      "slug": "consolidation",
      "title": "上下文与统一插件安装",
      "group": "INSTALL",
      "description": "安装 Context CLI、统一插件以及旧版本迁移。"
    },
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
      "description": "安装、Hook 接入、任务复核，以及当前 CLI / API 操作边界。"
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
