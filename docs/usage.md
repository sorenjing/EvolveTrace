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

部署内容包括根目录 `hooks/hooks.json`、`context/hooks/session_start.py` 与 `plugin/hooks/`。独立 audit-only 插件包装已退役；切换统一插件后停用旧安装，避免重复采集。

更新后若 Hook 显示 `modified` 或 `untrusted`，先重新审核当前定义，再开新会话。旧信任记录和数据库里的旧 Session 都不能证明新版已运行；具体核查顺序见[当前 Hook 信任与真实派发检查](observability.md#先确认当前-hook-定义已获信任)。

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

## 先看项目与会话

首屏默认显示「全部项目总览」。左侧项目下面是已采集会话，不是文件目录树；同一会话可能访问多个项目，因此可出现在多个项目中。选择项目后统计限定为该项目，选择会话后进一步限定为该项目中的这次会话；未归属会话仍可单独查看。中间「当前统计范围」始终说明正在看哪一组记录。

统计先取最近入库的最多 20,000 条事件，再应用筛选，不等于今天或全量历史。调用次数按关联标识尽量合并开始和结束事件；未知结果、仅捕获开始与失败分开。耗时只累计已有样本，并行调用耗时之和不是会话持续时间。全局采集状态单独折叠，不随项目筛选。

先看顶部“需要核对的线索”，使用“定位相关证据”检查输入与结果；再看“操作目的与结果”中每类的次数、失败、查询结果与耗时样本。脚本名称或组合结构推断会明确标出，复杂命令的目的保留待确认。没有规则命中不代表任务已经完成。

简单搜索的“无匹配”和显式 diff 查询的“有差异”可正常返回 1，单列为“无匹配／有差异”，不触发失败重试提醒。原始退出码保留；若 Task 明确要求退出 0，仍按原合同验收。详见[分类与查询结果边界](workspace-audit.md#统计范围与规则)。

按操作类型查看搜索读取、修改、构建测试、依赖、Git、网络、组合命令与其他工具；点击「这些数字怎么算」查看口径。提醒旁可展开阈值：同一会话最后已观察操作前 10 分钟，同命令同目录无已捕获修改的重复读取/构建至少 5 次，或连续失败至少 3 次。这些是当前启发式默认值，尚未按真实任务标定，不是公开行业标准，也不会自动阻断命令。历史提醒不表示当前仍在异常。

日常顺序为「选项目 → 看提醒 → 查看证据 → 需要时选择分析 → 核实后保存记忆」。任务验收折叠在左侧进阶入口，普通统计无需创建 Task。项目记忆与采集诊断也可按需展开。

## 工作台审查顺序

1. 选择 Task，确认目标、仓库范围、约束和验收条件。
2. 检查 Context Snapshot 与 Context Receipt 的来源和 freshness。
3. 检查 Run 是否绑定到正确 Session。
4. 在“执行流程”按顺序查看每一步。一次工具调用的开始与完成事件会合并为一步；点击后分别阅读右侧的“工具输入”和“工具输出”，长内容可在面板内滚动。未采集到完成事件时会明确标记，不能据此断定工具仍在运行。风险提示与其他采集字段也在右侧。
5. 对当前选中的 Run 运行确定性 Evaluation，逐项核对面板显示的 Session、Run ID 和 evidence refs。切换 Run 会清空旧评估和备注；其他会话的新事件只刷新数据，不自动切换当前审查对象。
6. 由人记录 `accepted` 或 `needs_fix`，不要把命令退出码直接等同于最终接受。
7. 标为“需修复”后，在“修正与复验”选择目标仓库，点击“准备修正运行”。这会重新激活该 Task，沿用原上下文与验收条件；所选仓库后续的新会话绑定到此 Task。请在目标仓库新开 Codex 会话，原会话始终属于旧 Run。
8. 匹配的新 Hook 到达后，从 Task Runs 选择新 Run。等待结束，运行评估并由人决定是否接受；旧评估和复核保持只读。
9. 在“修正与复验”选择需修复的原始 Run 和较新的已接受 Run，逐项核对规则版本、结果及证据，再点击“确认前后比较”。只有满足后端条件与回执检查的对比才会推进到 `effective`。确认保存具体 Run 对，刷新后可恢复，同一对请求重试不重复推进回执。缺少回执时显示错误，不会自动制造交付记录；`effective` 关联已复核的执行结果，不代表模型理解或因果收益。

旧版本只有 `effective` 回执而没有保存具体比较对时，不能据此认定当前选择已确认；历史回执不自动回退或补造比较记录。

只有活动 Task 接收新会话。进入待复核、需修复、已接受或已阻断后，旧租约不再自动创建新 Run；已经绑定的会话仍可补充采集记录。阻断的任务保留历史，不能通过“准备修正运行”直接恢复。

结构化验收条件必须逐项有评估结果。当前尚未接入服务的 `file_exists` 与 `manual` 条件会返回 `needs_review`，不会默认算作通过：必需项为 `blocking`，阻止 `accepted`；可选项为 `warning`。填写普通复核说明不能覆盖必需项缺口。服务不会根据 Hook 提供的目录直接扫描本机文件。历史快照缺少条件时需创建新的 Run，不能自动补写或覆盖原评估。

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
