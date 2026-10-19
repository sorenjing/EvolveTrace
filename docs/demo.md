# 用合成数据查看 EvolveTrace

此演示只使用仓库内的公开合成 fixtures，无需接入真实 Codex 会话。
它展示 Task、Context Snapshot、Run 与执行时间线，不代表已经完成真实任务验收。

## 1. 准备环境

先完成 [README 的依赖安装与工作台构建](../README.md#快速开始)。下面使用独立端口 **8002** 和演示数据库，保留默认 8001 服务的数据。
请在一个新的 PowerShell 终端中，从仓库根目录运行后续命令。

## 2. 写入合成记录并启动演示服务

```powershell
cd backend
venv\Scripts\python.exe scripts/seed_demo.py

# seed_demo.py 固定写入这两个文件；服务必须读取同一组数据库
$env:EVOLVETRACE_DB_PATH = Join-Path (Get-Location) ".demo-audit.db"
$env:EVOLVETRACE_HARNESS_DB_PATH = Join-Path (Get-Location) ".demo-harness.db"
$env:EVOLVETRACE_STATIC_UI_DIR = Join-Path (Get-Location) "static"
venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8002
```

打开 `http://127.0.0.1:8002`。不要用 `start.ps1` 启动这组演示配置：该脚本使用默认端口 8001。
示例要求前端使用默认的同源 API 地址；如果构建时自定义了 `NEXT_PUBLIC_API_BASE_URL` 或 `NEXT_PUBLIC_BACKEND_URL`，需要先清除覆盖配置并重新构建。

演示数据库生成于 `backend/.demo-audit.db` 和 `backend/.demo-harness.db`；请勿提交数据库及 SQLite 辅助文件。
`Ctrl+C` 停止本次服务，关闭这个专用终端即可丢弃环境变量设置。
种子脚本不是重置工具，重复运行会保留已有演示记录；首次查看建议只执行一次。

## 3. 核对当前界面

1. 选择 `Verify sample export` 任务，查看目标、范围和 `sample-app` 上下文快照。
2. 在 Task Runs 中选择 `demo-session`，查看合成修改事件和 `npm test -- tests/example.test.ts` 命令。
3. 核对证据边界：fixture 没有提供该命令的结构化退出结果，也没有任务结束事件，不能据此宣称测试通过或任务完成。

这组最小 fixture 不展示已完成 Run 的评估面板。用于验证“缺少证据不可接受、修正后重新评估、人工复核与比较”的合成回归测试，可以在仓库根目录运行：

```powershell
cd backend
./venv/Scripts/python.exe -m pytest tests/test_evaluation_replay.py -q
```

## 评估与修正比较的入口

工作台支持已结束 Run 的确定性评估和人工 Review Decision。
Task 创建、Context 导入与首次活动任务设置通过 Context CLI / HTTP API 完成。标为“需修复”后，工作台可准备新尝试，并在新 Run 经评估和人工接受后展示前后结果与确认比较；执行修正仍需新开 Codex 会话。
证据交接链路见[上下文证据演示](context-evidence-demo.md)，启动本地服务后可在 `/docs` 查看 HTTP API 契约；通用案例导入导出和重放仍在路线图中。

## 接入自己的执行

按[合并使用指南](consolidation.md)安装并启用统一插件，在默认本地服务上确认新事件进入工作台。
统一插件使用 `plugin/hooks/` 中的采集与安全实现。普通采集在后端关闭时降级为证据缺失，本地 Safety Sentinel 的拒绝判断仍独立返回。
模式脱敏不能保证清除任意自由文本中的敏感信息，参见 [Hook 契约](hook-event-contract.md)。
