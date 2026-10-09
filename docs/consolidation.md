# 合并后的安装、使用与远程迁移

EvolveTrace 的 `context/` 维护 AI Context Kit 上下文组件；`backend/` 与 `src/` 维护执行证据和审查工作台。`aictx` 仍可独立使用，后端仍通过版本化 JSON 接收上下文。Marlow 保持独立。

## 本地安装

在 EvolveTrace 根目录安装上下文组件：

```powershell
python -m pip install ./context
aictx --version
```

开发环境可运行 `python -m pip install -e "./context[dev]"`。如果使用 pipx，先用 `pipx list` 检查已有安装，再用 `pipx install --force ./context` 替换它。曾手写 aictx 启动器的用户应检查 `Get-Command aictx -All`，避免 PATH 中较早的旧启动器遮蔽新安装。

工作区 `.aictx.toml` 和 `.ai/` 保持原位，不要复制到组件目录或重新初始化第二套记忆。

```powershell
aictx status --workspace <工作区根目录>
aictx load <项目名> --workspace <工作区根目录>
aictx usage <项目名> --workspace <工作区根目录>
```

CLI 仍只观察规定范围的元数据、加载选定项目记忆。自动筛选对话、语义检索和新旧事实冲突处理不属于本次合并实现。

## 统一插件

```powershell
python scripts/build_plugin_archive.py
```

输出 `dist/evolvetrace-plugin.zip`。上传该文件，启用统一 EvolveTrace 插件，再停用以前单独安装的 AI Context Kit 和 audit-only EvolveTrace 插件，避免重复加载与采集。首次安装先保留旧安装作为回退，确认新插件可用后再卸载旧插件。

ZIP 根目录直接包含 `.codex-plugin/plugin.json`，并同时包含上下文 Skill、SessionStart 加载器和原有审计 Hook。插件不包含后端、Python CLI、私人工作区记忆或数据库；CLI 和本地服务需要分别安装、运行。

旧 `plugin/` 目录继续提供 audit-only 接入，不包含上下文加载。`context/` 中的旧独立插件入口保留兼容性；日常使用优先安装仓库根目录的统一插件。

```powershell
./start.ps1 -NoBrowser
```

打开 `http://127.0.0.1:8001`。在新的项目会话中检查上下文加载消息，用 `aictx usage` 核查来源，再运行 `./scripts/observe.ps1 -ExpectEvidence` 核查执行证据。上下文输出成功不能单独证明客户端接收、模型采用或任务收益。

需要把任务与执行绑定时：

```powershell
aictx task prepare <项目名> --intent "本次任务目标" --platform codex
aictx task submit <task-id> --evolvetrace-url http://127.0.0.1:8001
```

## GitHub 迁移顺序

1. 主仓库为 `sorenjing/EvolveTrace`，继续使用 `master`，保留原应用历史和导入的上下文组件历史。
2. 将合并提交发布到主仓库，等待根目录 CI 通过。
3. 以已发布的完整提交 SHA 验证远程子目录安装：

   ```powershell
   pipx install "git+https://github.com/sorenjing/EvolveTrace.git@<已发布提交SHA>#subdirectory=context"
   ```

4. 如果有插件市场或安装脚本，改为主仓库根目录的统一插件来源，并在客户端实际刷新、验证。插件市场同步与 CLI 更新是两件事。
5. 更新旧 `sorenjing/ai-context-kit` README，说明后续开发位于 `EvolveTrace/context`，保留旧版本、历史和问题记录。
6. 新安装与旧安装回退均已验证后，将旧仓库归档。无需删除仓库、强推历史、重命名主仓库或覆盖旧标签。

发布前优先使用本地目录安装。上述远程命令只有在合并提交已经存在于 GitHub 时才有效。

## CI、包发布与许可证

根目录 CI 分别验证上下文组件、插件归档、后端和前端。`context/.github/` 是原仓库历史，不作为主仓库工作流运行。

Python 包保持 `ai-context-kit` 名称。组件发布使用 `context-v<版本>` 标签；应用的普通版本标签不会触发组件发布。迁移到新仓库后，需要先配置对应的 GitHub `pypi` environment 和 PyPI trusted publisher。合并本身不发布 PyPI 包。

EvolveTrace 使用 Apache-2.0；`context/` 保留 MIT。许可证和来源说明见根目录 `NOTICE` 与两个 `LICENSE` 文件。
