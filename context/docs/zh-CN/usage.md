本组件现维护于 EvolveTrace/context。首次安装请先阅读[合并使用指南](../../../docs/consolidation.md)；远程命令需要填写已发布的提交 SHA。

# AI Context Kit 中文使用手册

AI Context Kit 在一个工作区内维护共享的 `.ai/` 上下文，让 Codex、Claude、Gemini 和 Cursor 使用同一套项目索引与语义记忆。它读取有限的项目元数据，不替代当前源码、测试或项目规则。

## 安装方式

### 正式使用

在首次 PyPI 发布前，从 Git 仓库安装：

```powershell
pipx install "git+https://github.com/sorenjing/EvolveTrace.git@<已发布提交SHA>#subdirectory=context"
aictx --version
```

这种方式适合普通使用者，运行环境和项目源码相互隔离。

### 本地开发

需要修改 AI Context Kit 本身时，在仓库中创建虚拟环境并安装开发依赖：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\aictx.exe --version
```

如果使用包装脚本通过 `PYTHONPATH` 指向源码，应将它视为开发连接。仓库移动后需要同步更新包装脚本。

## 初始化工作区

在包含多个项目的共同上级目录运行：

```powershell
aictx init --dry-run
aictx init
aictx status
aictx check
```

工作区只保留一套 `.ai/`。不要在每个子项目里重复初始化。

## 每次开始工作

### 直接查看是否实际加载

下面的命令对应包含本次加载实现的源码。如果 `aictx --help` 中没有 `load`、`usage`，先更新 CLI；插件和 CLI 是两个独立安装，需要同时更新。尚未发布的改动可通过上面的本地开发方式使用，不能假定 GitHub 安装已经包含它们。

在工作区根目录指定项目，或在项目目录中省略项目名：

```powershell
aictx load <项目名> --workspace <工作区路径>
aictx usage <项目名> --workspace <工作区路径>
```

`load` 实际读取文件并把正文输出给调用方；终端里手动运行只表示终端收到输出，AI 仍需通过工具调用取得该输出。`usage` 是只读查询，显示最后一次触发时间、项目、真实读取的相对路径、字节数、SHA-256、新鲜度和缺口。安装成功但没有调用时会显示没有使用记录。

Codex 加载并信任插件 Hook 后，SessionStart 会自动执行相同加载流程，并返回简短 `systemMessage` 和上下文正文。它只匹配当前工作目录所属项目；在工作区根目录启动时只加载公共约定和索引，明确提示 `project_required`。一个会话中切换项目仍应调用定向 `load`，不会因为聊天中提到项目名就猜测要加载哪一个。

| 使用状态 | 含义 |
| --- | --- |
| `returned` | 三个来源均成功读取，观察的新鲜度正常，正文已输出到本地调用方 |
| `partial` | 返回了部分上下文或带有缺口；检查 `Attention`，不能当完整成功 |
| `blocked` | 没有可交付的记忆正文；检查工作区配置和缺失来源 |
| `model_use: unknown` | 没有模型采用或理解的证据，不能从输出状态推断效果 |

`stale/new/unknown` 会明确显示，不自动刷新记忆或编写语义结论。CLI `load` 退出码为 `0`（正常）、`1`（部分或阻塞）；Hook 返回非阻断提示，不阻止 Codex 启动。`usage` 退出码 `2` 表示记录或配置无法读取。

自动加载只包括 `.ai/GLOBAL.md`、`.ai/WORKSPACE.md`、匹配项目的 `.ai/projects/<project>.md`。不会读取其他项目正文、普通源码、CURRENT、额外 `context_sources` 或任务日志；这些仍按任务另行选择。每文件上限为 8 KiB（同时遵守更小的 `max_file_bytes`），总正文上限 16 KiB。过大的文件整份拒绝并提示，避免静默截断关键约束；软链接和 Windows junction 也会拒绝。Hook 的上下文上限为 20,000 个近似 Token，给受限正文及提示留余量，实际返回字节数不等于模型 Token 数。

记录只保存在工作区的 `.ai/usage.json`，滚动保留最近 20 次事件；不保存正文、提示词、机器绝对路径或原始会话 ID。不读写旧的 `.ai/tasks/*/receipt.json`，也不会把旧 `generated` 状态改成成功。记录损坏时保留原文件并提示 `usage_not_recorded`，不覆盖。工作区不可写时会提示记录失败；已返回的正文仍不能证明宿主接收。

第一次验证：在选中项目内新开启用插件的 Codex 会话，之后运行 `aictx usage <项目名>`，确认时间、`SessionStart:startup`、来源和 `Attention`。手工 `load` 的触发类型为 `manual`，不能冒充宿主 Hook 事件。宿主是否使用了正文、产物是否遵守约束，需要单独核对任务证据，见[效果验证](effectiveness.md)。

### 手工兜底

如果 `Attention` 显示 `semantic_memory_empty`，该项目 manual 区仍是默认模板或空白。CLI 可以交付检测事实，但目标、设计决策和任务约束还没有记录；按当前项目权威资料人工补充，不能把 `current` 当作业务背景已经齐全。

1. 阅读 `.ai/GLOBAL.md`。
2. 阅读 `.ai/WORKSPACE.md`。
3. 只加载当前项目对应的 `.ai/projects/<project>.md`。
4. 运行 `aictx status`。
5. 任务依赖未观察的源码行为时，直接检查当前源码和测试。

`current` 只表示上次渲染时观察的输入没有变化，不证明整个项目实现仍然正确。

## 状态含义

| 状态 | 含义 | 推荐动作 |
| --- | --- | --- |
| `new` | 已发现项目，但还没有生成项目记忆 | 先运行定向 `update --dry-run` |
| `stale` | 被观察的 README、清单或 Git 元数据已变化 | 审阅定向更新 |
| `current` | 被观察的输入与上次渲染一致 | 仍按任务需要检查源码 |
| `missing` | 状态中记录的项目已不再被发现 | 确认是删除、移动、改名还是发现配置变化 |

## 安全更新流程

优先更新单个项目：

```powershell
aictx update <项目名> --dry-run
aictx update <项目名>
aictx check
aictx usage
```

只有明确需要同步整个工作区时才省略项目名，并且仍然先使用 `--dry-run`。

项目文件包含两类标记区：

- `auto` 区由 CLI 维护，不手工编辑。
- `manual` 区保存目标、决策、约束、当前状态和已知问题。

不要把源码副本、完整聊天记录或命令日志写入 manual 区。

## 仓库变化后的处理

### 新增仓库

运行 `aictx scan` 确认发现结果，再对显示为 `new` 的项目执行定向 dry-run 和更新。

### 删除仓库

先确认 Git 与本地资产已经妥善处理。随后运行 `aictx status`，审阅 `missing` 项目，再执行全工作区 dry-run，让生成的索引与当前目录一致。

### 改名或移动仓库

先运行 `aictx scan` 检查新身份。目录移动可能表现为旧项目 `missing` 加新项目 `new`，不要在未核对身份前直接接受批量更新。

## 常用检查

```powershell
aictx --version
aictx scan
aictx status
aictx check
```

仓库提供的只读自检脚本会按这个顺序运行，并汇总退出状态。详见 [自测手册](self-check.md)。

## Personal AI Pack

Personal AI Pack 的安装完整性由 `aictx doctor --target <目标目录>` 检查。它不检查普通 `.ai` 工作区；普通工作区使用 `scan`、`status` 和 `check`。

## 隐私边界

- 不要把私人 Manifest、机器绝对路径或私人仓库映射提交到公共仓库。
- `publish github` 只生成待审阅文件，不会自动推送；发布前仍需检查内容和目标仓库权限。
- 工具默认离线。显式的本地 EvolveTrace 提交是单独的可选流程。
