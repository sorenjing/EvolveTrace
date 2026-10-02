# AI Context Kit 自测手册

这份手册用于回答两个问题：CLI 是否能正常运行，以及指定工作区是否需要维护。默认自测是只读的，不执行初始化、更新、安装或删除。

## 一键只读检查

从 AI Context Kit 仓库运行：

```powershell
./scripts/self-check.ps1 -Workspace <工作区路径>
```

脚本依次执行：

```text
aictx --version
aictx scan --workspace <工作区路径>
aictx status --workspace <工作区路径>
aictx check --workspace <工作区路径>
```

### 退出码

| 退出码 | 含义 |
| ---: | --- |
| `0` | CLI、项目发现、freshness 和结构完整性均正常 |
| `1` | CLI 可用，但存在 `new`、`stale`、`missing` 或结构问题，需要人工维护 |
| `2` | 工作区路径、配置、CLI 或项目发现无法正常运行 |

退出码 `1` 不表示工具损坏。它通常说明工具正确发现了工作区变化。

## 手工检查

### 1. CLI

```powershell
aictx --version
aictx --help
```

确认实际执行版本与预期安装方式一致。如果命令来自源码包装脚本，还应确认包装脚本指向当前仓库路径。

### 2. 普通工作区

```powershell
aictx scan --workspace <工作区路径>
aictx status --workspace <工作区路径>
aictx check --workspace <工作区路径>
```

- `scan` 验证项目发现。
- `status` 检查观察输入是否变化。
- `aictx check` 验证项目记忆标记和 AI 工具入口是否完整。

发现问题后按照 [中文使用手册](usage.md) 的 dry-run 流程处理，不要让自测脚本自动修改工作区。

### 3. 项目源码开发

在 AI Context Kit 仓库中运行：

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m build
```

测试通过只能证明代码层检查通过，不能替代目标工作区的 `status` 和 `check`。

### 4. Personal AI Pack

```powershell
aictx status --pack-target <安装目标>
aictx doctor --target <安装目标>
```

`aictx doctor` 只验证 Pack 管理文件及摘要，不检查普通工作区中的 `.ai` 项目记忆。

## 常见结果

### `status` 显示 stale

先运行定向 `aictx update <项目名> --dry-run`，确认自动事实变化合理，再应用并运行 `aictx check`。

### `status` 显示 missing

确认项目是否被删除、移动、改名或排除。不要仅为了让检查变绿而盲目更新。

### `check` 报 missing project memory

项目已经被发现，但对应项目记忆尚未生成。按 dry-run 流程更新该项目。

### CLI 找不到

检查安装工具、虚拟环境或源码包装脚本。正式安装和源码开发连接应分开管理，避免无法判断当前执行的是哪一份代码。
