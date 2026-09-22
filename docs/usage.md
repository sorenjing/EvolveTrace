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

仓库的 `plugin/` 是带生命周期 Hooks 的 Codex 插件包。使用支持本地插件的 Codex 客户端安装并启用该目录，并确认 `plugin/hooks/hooks.json` 随插件一起部署到本机执行环境。官方插件说明强调：仅在网页端安装不会把本地 Hook 脚本部署到执行机器，Hook 必须在本地可用。参见 [OpenAI 插件架构](https://developers.openai.com/plugins/concepts/plugins)。

插件会把支持的 Codex Hook 事件脱敏后发送到：

```text
http://127.0.0.1:8001/api/audit/events
```

普通采集是 best-effort：后端未启动或请求失败不会阻断正常任务。少数高置信度危险命令由插件本地的 Safety Sentinel 在 `PreToolUse` 阶段判断，因此不依赖后端可用性。

## 使用 AI Context Kit 创建任务证据链

先让 AI Context Kit 为目标项目准备有范围的任务合同：

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
4. 按时间线核对工具调用、修改、失败、权限和风险事件。
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
