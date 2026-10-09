# AI Context Kit 发布准备设计

## 目标

把已可安装的 0.1.0 CLI 补齐为可正式发布、可核验版本的开源包。此次只准备发布材料和自动化，不创建 Git tag、GitHub Release 或 PyPI 发布。

## CLI 与版本

`aictx --version` 输出包名和当前版本，版本来源保持单一，避免 CLI、包元数据和文档各自维护不同值。现有命令及退出码保持兼容。

## 发布自动化

CI 继续覆盖三个操作系统和三个 Python 版本。发布工作流只在符合 `v*` 的 tag 上触发，先构建 wheel 和 sdist、安装 wheel 并执行命令烟雾测试，再通过 PyPI Trusted Publishing 发布。仓库未配置对应 GitHub Environment 和 PyPI Trusted Publisher 时不得创建 tag。

新增 CHANGELOG 和发布说明，记录版本检查、测试、构建、安装验证、tag 与回滚边界。README 在正式发布前不把 PyPI 安装描述成已经可用，提供从 Git 仓库安装的真实命令。

## 验收

- `aictx --version` 有自动化测试，并且版本与构建元数据一致。
- wheel 和 sdist 可以本地构建，wheel 可在隔离环境安装并运行 `aictx --version`。
- CHANGELOG、发布文档和 tag 工作流互相一致。
- 不执行任何外部发布动作。

