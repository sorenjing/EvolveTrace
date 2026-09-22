# EvolveTrace 观测与排障手册

EvolveTrace 观察的是 Coding Agent 公开暴露的工程事件和验证结果。它不读取隐藏思维链，也不能仅凭没有事件就证明某个动作没有发生。

## 一键只读观测

服务启动后，在仓库根目录运行：

```powershell
./scripts/observe.ps1
```

需要验证 Hook 确实产生了证据时：

```powershell
./scripts/observe.ps1 -ExpectEvidence
```

脚本只执行 GET 请求，不写数据库、不生成演示数据、不运行 Evaluation，也不记录 Review。

### 退出码

| 退出码 | 含义 |
| ---: | --- |
| `0` | 服务、工作台和只读 API 可访问；若启用 `-ExpectEvidence`，至少存在一个 Session |
| `1` | 服务正常，但启用 `-ExpectEvidence` 后仍没有 Hook 证据 |
| `2` | 服务、工作台或只读 API 无法访问 |

## 第一层：服务和工作台

检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
Invoke-WebRequest http://127.0.0.1:8001/ -UseBasicParsing
```

正常状态是 `/health` 返回成功状态，首页返回 HTTP 200。失败时依次检查：

1. `backend/venv/Scripts/uvicorn.exe` 是否存在。
2. `start.ps1` 是否打印 ready。
3. `8001` 是否被其他进程占用。
4. `backend/static` 是否已由 `scripts/build_static_ui.ps1` 生成。

## 第二层：Hook 是否到达

查看会话摘要：

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/audit/sessions
```

在 Codex 中执行一个会触发生命周期或工具事件的任务后，应该出现新的 Session 或现有 Session 的事件计数增加。

没有事件时检查：

1. Codex 客户端是否安装并启用了 `plugin/`。
2. 本地执行环境是否实际包含 `plugin/hooks/hooks.json` 和 Python 采集脚本。
3. Hook 使用的 Python 是否可运行。
4. 服务是否在事件发生时监听 `127.0.0.1:8001`。
5. 后端控制台是否报告格式校验或请求错误。

采集是 best-effort。没有 Hook 记录只能说明当前证据不足。

## 第三层：Session 和 Event 证据

列出 Session：

```text
GET /api/audit/sessions
```

查看单个 Session：

```text
GET /api/audit/sessions/{session_id}
```

重点核对：

- 事件是否按时间顺序出现。
- `cwd` 是否对应预期仓库。
- 工具名、退出状态和修改范围是否合理。
- 敏感值是否显示为脱敏值。
- 风险说明是否来自确定性规则，而非隐藏推理。
- SessionStart、Stop 等边界事件是否存在；缺失时将证据标记为不完整。

## 第四层：Task、Run 与绑定

检查任务和未绑定运行：

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/harness/tasks
Invoke-RestMethod http://127.0.0.1:8001/api/harness/runs/unbound
```

正常绑定需要活动 Task 的仓库范围与 Hook 的 `cwd` 匹配。Unbound Runs 不一定是程序错误，常见原因包括：

- 尚未激活 Task。
- Task 的 repository path 与真实 `cwd` 不一致。
- 在父工作区或嵌套仓库中启动了 Codex。
- Hook 先于任务提交到达。

不要为了消除 Unbound Runs 而修改历史证据；先核对仓库身份与任务范围。

## 第五层：Evaluation 与 Review

在工作台对目标 Run 运行确定性 Evaluation，并核对：

- 每个 criterion 的 `passed`、`failed`、`needs_review` 或 `skipped` 状态。
- `expected` 和 `actual` 是否可比较。
- `evidence_refs` 是否指向当前 Run 的真实证据。
- 缺少验证命令时是否明确失败或需要复核。

Review 是人的不可变决定。`accepted` 应建立在当前 Evaluation 与实际代码审查之上；`needs_fix` 应写明缺失证据或需要修正的行为。

## Context Receipt 状态怎么解释

| 状态 | 能证明什么 | 不能证明什么 |
| --- | --- | --- |
| `generated` | receipt 已在本地产生 | 未证明已送达 |
| `delivered` | 证据接收端接受了有限身份信息 | 未证明 Agent 已读取 |
| `acknowledged` | 某次可观察执行已绑定任务 | 未证明理解或遵循 |
| `evidenced` | 输出证据引用了受治理的上下文身份 | 未证明效果更好 |
| `effective` | 经复核的前后对比支持有效性判断 | 不代表对所有任务都有效 |

任何状态都不提供隐藏思维链，也不替代当前源码检查。

## 数据库层排障

默认文件位于操作系统临时目录的 `evolvetrace` 子目录。服务停止后可以确认文件是否存在和更新时间，但不要在服务运行时手工修改 SQLite。

如果 API 健康但旧数据消失，检查：

- 操作系统临时目录是否被清理。
- `EVOLVETRACE_HARNESS_DB_PATH` 是否变化。
- 当前启动用户是否与之前一致。
- 是否误用了演示数据库或另一套虚拟环境。

## 观测仍然不能替代什么

- Git diff、测试、lint、build 和人工代码审查。
- 操作系统级沙箱。
- 对未暴露 Hook 路径的完整审计。
- 对 Agent 意图、理解或隐藏思维链的判断。
- 对单次成功运行的普遍因果结论。
