# AI Context Kit 中文使用手册

AI Context Kit 在一个工作区内维护共享的 `.ai/` 上下文，让 Codex、Claude、Gemini 和 Cursor 使用同一套项目索引与语义记忆。它读取有限的项目元数据，不替代当前源码、测试或项目规则。

## 安装方式

### 正式使用

在首次 PyPI 发布前，从 Git 仓库安装：

```powershell
pipx install git+https://github.com/sorenjing/ai-context-kit.git
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
