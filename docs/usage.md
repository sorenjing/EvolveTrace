# EvolveTrace 中文使用手册

EvolveTrace 是本地运行的 Coding Agent 证据、评估与复核工作台。普通使用只需要一个 FastAPI 进程：它在 `127.0.0.1:8001` 同时提供 API、SSE 和已构建的静态工作台。

## 一次性准备

### 后端

```powershell
cd backend
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements-dev.txt
cd ..
```

### 静态工作台

```powershell
./scripts/build_static_ui.ps1
```

该命令安装前端依赖、执行 Next.js 构建，并把静态产物复制到 `backend/static`。只有前端代码变化后才需要重新构建。

## 普通启动

```powershell
./start.ps1
```

脚本只启动本地 Uvicorn，等待 `http://127.0.0.1:8001/health` 可用，然后打开：

```text
http://127.0.0.1:8001
```

在 ChatGPT 桌面版 Codex 中使用：

```powershell
./start.ps1 -NoBrowser
```

然后让 Codex 的 `@Browser` 打开 `http://127.0.0.1:8001`。按任意键会停止本次启动的后端进程。

端口 `3000` 只属于下一节的前端热更新开发模式，不是普通使用入口。

## 开发模式

后端终端：

```powershell
cd backend
venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8001 --reload
```

前端终端：

```powershell
npm install
npm run dev
```

此时前端热更新入口是 `http://127.0.0.1:3000`，API 仍然在 `8001`。不要把后端监听地址改成公共网卡。

## 接入 Codex Hook

日常安装使用仓库根目录的统一插件，它同时加载 EvolveTrace Context 和采集执行事件。先在仓库根目录安装 CLI 并生成插件 ZIP：

```powershell
python -m pip install ./context
python scripts/build_plugin_archive.py
```

在支持本地插件的 Codex 客户端上传 `dist/evolvetrace-plugin.zip`，或通过插件市场安装仓库根目录；启用后审核并信任 Hook，再开启新的项目会话。CLI 可用 `/hooks` 核查当前定义和信任状态。安装或启用插件本身不会自动信任 Hook，网页安装也不会把脚本部署到本机。参见 [官方 Hook 文档](https://learn.chatgpt.com/docs/hooks) 和[合并安装指南](consolidation.md)。

部署内容包括根目录 `hooks/hooks.json`、`context/hooks/session_start.py` 与 `plugin/hooks/`。旧 `plugin/` 只提供 audit-only 兼容接入，不加载上下文；切换统一插件后停用旧插件，避免重复采集。

插件会把支持的 Codex Hook 事件脱敏后发送到：

```text
http://127.0.0.1:8001/api/audit/events
```

普通采集是 best-effort：后端未启动或请求失败不会阻断正常任务。少数高置信度危险命令由插件本地的 Safety Sentinel 在 `PreToolUse` 阶段判断，因此不依赖后端可用性。

## 使用 EvolveTrace Context 创建任务证据链

先让 EvolveTrace Context 为目标项目准备有范围的任务合同：

```powershell
aictx task prepare <项目名> --intent "本次任务目标" --platform codex
```

启动 EvolveTrace 后，提交生成的任务：

```powershell
aictx task submit <task-id> --evolvetrace-url http://127.0.0.1:8001
```

随后在目标仓库执行 Codex 任务。匹配的 Hook 会话会绑定到活动 Task 和 Run；路径无法匹配时会进入 Unbound Runs，等待人工核对。

## 工作台审查顺序

1. 选择 Task，确认目标、仓库范围、约束和验收条件。
2. 检查 Context Snapshot 与 Context Receipt 的来源和 freshness。
3. 检查 Run 是否绑定到正确 Session。
4. 在“执行流程”按顺序查看每一步。一次工具调用的开始与完成事件会合并为一步；点击后分别阅读右侧的“工具输入”和“工具输出”，长内容可在面板内滚动。未采集到完成事件时会明确标记，不能据此断定工具仍在运行。风险提示与其他采集字段也在右侧。
5. 运行确定性 Evaluation，逐项核对 evidence refs。
6. 由人记录 `accepted` 或 `needs_fix`，不要把命令退出码直接等同于最终接受。
7. 修正后比较两个 Run；只有经过复核的对比才可能把 receipt 推进到 `effective`。

## 数据位置与清理边界

默认审计数据库和 Harness 数据库存放在操作系统临时目录下的 `evolvetrace` 目录，而不是 Git 仓库：

```text
<临时目录>/evolvetrace/audit.db
<临时目录>/evolvetrace/harness.db
```

`EVOLVETRACE_HARNESS_DB_PATH` 可以覆盖 Harness 数据库位置。删除数据库会丢失本地证据、任务、评估和复核记录；清理前应先停止服务并确认数据不再需要。

演示数据库使用 `backend/.demo-audit.db` 和 `backend/.demo-harness.db`，与默认运行数据分开。

## 停止与恢复

- `start.ps1` 启动的服务按任意键停止。
- 再次启动会继续使用默认数据库中的既有记录。
- Hook 采集失败不会自动补发；后端停机期间的普通事件可能缺失。
- Hook 缺失意味着证据不完整，不能据此推断某个动作没有发生。

## 自测与观测

只读检查命令：

```powershell
./scripts/observe.ps1
./scripts/observe.ps1 -ExpectEvidence
```

详细解释见 [观测与排障手册](observability.md)。无需真实 Codex 的合成演示见 [demo.md](demo.md)。
