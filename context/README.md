# AI Context Kit

The independently installable context component of EvolveTrace. Source, development and unified plugin packaging are maintained in this monorepo. See [installation and migration](../docs/consolidation.md).

From the monorepo root: `python -m pip install ./context`. Inside this directory: `python -m pip install .`. Remote subdirectory installation requires an already-published consolidation commit.

[![CI](https://github.com/sorenjing/EvolveTrace/actions/workflows/ci.yml/badge.svg)](https://github.com/sorenjing/EvolveTrace/actions/workflows/ci.yml) [![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/) [![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Auditable project context shared across AI coding tools.**

AI Context Kit maintains compact project observations that Codex, Claude, Gemini, and Cursor can read from the same workspace. It discovers nested projects, records facts from a bounded set of metadata, and detects when those observed inputs change.

No model API, cloud service, or vector database is required. The result is a small, reviewable `.ai/` directory that can be version-controlled and shared.

The repository and its current files remain authoritative. AI Context Kit provides a reusable observation and memory layer; it does not replace source inspection or project rules.

For a reproducible comparison against ordinary repository inspection, see the
[context delivery evaluation procedure](docs/context-evaluation.md). It records
source coverage and task checks without treating a delivered bundle as proof of
model understanding.

## Why this exists

AI assistants usually keep instructions at the project level, while related projects often live in a larger workspace. That creates two kinds of waste:

- every tool repeats the same repository discovery;
- useful decisions stay trapped in one project folder or one assistant session.

AI Context Kit gives the workspace one shared context entry point. The CLI owns deterministic observations and change detection; people and their assistants own the short semantic memory that explains goals, decisions, constraints, and current state.

## What you get

- **One context store** shared by four AI tools through thin `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, and Cursor entries.
- **Incremental refresh** based on metadata fingerprints instead of a full re-analysis every time.
- **Auditable scope** recorded beside generated facts, so readers can see which bounded inputs were observed.
- **Observable loading** through `aictx load <project>` and read-only `aictx usage [project]`; the Codex session hook returns bounded context and records metadata, without claiming model comprehension.
- **Human-safe memory** with protected manual blocks that the CLI will not overwrite.
- **Cross-process write safety** so concurrent terminals or agents do not lose workspace updates.
- **Offline by default**: recognized manifests, bounded README text, Git metadata, and directory names only.
- **Safe failure modes** for malformed markers, symlinked discovery roots, secret files, and project-name collisions.

## How it fits with agent skills

AI Context Kit is the **shared context layer**. It can be used alongside reusable Agent Skills and repository-local rules without depending on either one. See [Agent Skills integration](docs/integrations/agent-skills.md) for the runtime composition and responsibility boundaries.

## Plugin and web access

The standard plugin package exposes `manage-ai-context` from the canonical `skills/` directory and delegates deterministic local work to the `aictx` CLI.

The SessionStart hook now loads only shared GLOBAL/WORKSPACE context and the matching project memory. Update both CLI and plugin to a revision containing this implementation; older installations only provide a reminder. Run `aictx usage <project>` to inspect actual loading evidence and gaps. See [中文使用手册](docs/zh-CN/usage.md#直接查看是否实际加载) for startup, project switching, and state meanings.

For ChatGPT web access, the repository includes a read-only GitHub-backed MCP server and container deployment. Exported context becomes available after the reviewed publication tree is committed to GitHub and the MCP server is deployed at a stable HTTPS URL. See [GitHub-backed web MVP](docs/github-web-mvp.md) for setup and [Plugin architecture](docs/plugin-architecture.md) for the wider design.

Local writers and the remote reader use different resource controls. See [Runtime concurrency and process model](docs/runtime-concurrency.md) for file locking, atomic replacement, MCP backpressure, multi-worker sizing, and failure guarantees.

## Install

AI Context Kit requires Python 3.11 or newer.

Before the first PyPI release, install directly from the repository:

```bash
pipx install "git+https://github.com/sorenjing/EvolveTrace.git@<published-commit-sha>#subdirectory=context"
```

After the first PyPI release, `pipx install ai-context-kit` will become the preferred command. The current version is installed directly from GitHub.

For local development:

```bash
python -m pip install -e ".[dev]"
```

## Quick start

From the directory containing your projects:

```bash
aictx init --dry-run
aictx init
aictx status
```

The workspace will contain:

```text
.aictx.toml
.ai/
  GLOBAL.md
  WORKSPACE.md
  CURRENT.md
  state.json
  projects/
AGENTS.md
CLAUDE.md
GEMINI.md
.cursor/rules/ai-context.mdc
```

When a manifest or README changes:

```bash
aictx status
aictx update my-project --dry-run
aictx update my-project
aictx check
```

Commands:

- `aictx init`: create the workspace, adapters, and first project facts.
- `aictx scan`: print discovered projects without writing context.
- `aictx status`: report `new`, `stale`, `current`, or `missing` projects. `current` means the observed inputs match the last render; it does not guarantee that every project fact is complete or correct.
- `aictx update [project]`: refresh all projects or one selected project.
- `aictx check`: validate project-memory markers and adapter presence.
- `aictx repo inspect [path] [--json] [--context-commit SHA]`: inspect local Git state and compare a context commit with HEAD and cached upstream refs. This command never fetches or changes the repository.
- `aictx locate --manifest <path> --start <path> --json`: resolve a Personal AI Pack workspace and Portfolio through explicit paths, environment variables, a machine-local override, or bounded discovery.
- `aictx export chatgpt-project <project>`: render a portable context file for upload to a matching ChatGPT Project.
- `aictx export harness <project> --format json --output -`: print a versioned, local `ContextBundle v1` for an AI development harness.

- `aictx publish github <project>`: write a deterministic, commit-ready bundle and index to `.ai/published` for explicit review.
- `aictx task prepare <project> --intent <text> --platform codex`: create a v1 task-bound envelope, bundle, receipt, and handoff under `.ai/tasks/`.
- `aictx task prepare <project> --intent <text> --contract examples/task-contract-v2.json`: create a v2 envelope with reviewed repository scope, constraints, and structured acceptance criteria.
- `aictx task submit <task-id> --evolvetrace-url http://127.0.0.1:8000`: send those contracts to an optional loopback EvolveTrace instance.

For a repeatable comparison with ordinary repository search, see the [ContextBundle evaluation method](docs/context-bundle-evaluation.md). A generated bundle alone does not establish task efficiency.

Use `--workspace PATH` from outside the workspace. Mutating commands support `--dry-run`.

## Install a Personal AI Pack

A Personal AI Pack is a private manifest that references context and Skill authorities
without embedding their content in the public plugin:

```bash
aictx setup --manifest personal-ai-pack.yaml
aictx install --manifest personal-ai-pack.yaml --target ~/.local/share/aictx
aictx status --pack-target ~/.local/share/aictx
aictx doctor --target ~/.local/share/aictx
aictx update --manifest personal-ai-pack.yaml --target ~/.local/share/aictx
aictx uninstall --target ~/.local/share/aictx
```

The state stores only pack identity, enabled platforms, managed relative paths, and
digests. It never stores the manifest location, credentials, private source bodies, or
local repository paths. The repository includes only a synthetic example at
`examples/personal-ai-pack.example.json`.

The original `personal-ai-pack/v1` contract remains supported. Version 2 adds one
shared entry policy and thin Local, Codex, and ChatGPT bootstrap/fallback entrypoints.
It does not copy source mappings into generated files. Installed assets live below the
explicit target's `.aictx-pack/generated/` directory and are covered by `doctor` digests.

When repository locations differ between machines, resolve them without committing
absolute paths:

```bash
export AICTX_WORKSPACE_ROOT=/path/to/workspace
export AICTX_PORTFOLIO_ROOT=/path/to/private-portfolio
aictx locate --manifest personal-ai-pack.yaml --start . --json
```

The precedence is explicit CLI arguments, `AICTX_` environment variables, an optional
untracked `.aictx.local.toml`, bounded discovery, then an unresolved or ambiguous
result. Discovery defaults to depth 3, does not follow directory symlinks, and excludes
Git metadata, dependency, virtual-environment, build, coverage, and generated context
directories. A tracked local override is rejected because it may contain private
machine paths.

Generated prompts are recovery and bootstrap assets, not a replacement for the Pack,
Skill, MCP, repository rules, or current source inspection. ChatGPT still requires a
deployed HTTPS MCP, an authorized GitHub Connector, or a reviewed Project handoff; the
installer does not register those platform-side connections.

## Use with ChatGPT Projects

AI Context Kit can generate a compact project handoff for ChatGPT Projects:

```bash
aictx export chatgpt-project my-project
```

The command writes `.ai/exports/my-project-chatgpt-project.md`. Upload that file to the matching ChatGPT Project as a source, then start task-specific chats inside the Project. Regenerate and replace the upload after meaningful project changes.

The export combines bounded automatic facts, the selected project's managed semantic memory, and `GLOBAL.md`. It is a portable context file, not a way to read, write, or synchronize ChatGPT saved memory. Keep the workspace and its repository files as the source of truth, and do not upload secrets or private material that should stay outside ChatGPT.

ChatGPT Projects organize shared chats, files, instructions, and sources; ChatGPT saved memory is a separate recall layer. See the official documentation for [Projects](https://learn.chatgpt.com/docs/projects) and [Memories](https://learn.chatgpt.com/docs/customization/memories).

## Use with EvolveTrace

EvolveTrace consumes a stable JSON handoff rather than AI Context Kit internals or human-facing Markdown:

```bash
aictx export harness my-project --format json --output -
```

The command emits `context-bundle/v1` with the selected project, generation time, freshness state, bounded observation scope, workspace-relative repository identifier, and automatic/manual/shared context. It performs no network requests and does not mutate the workspace when `--output -` is used.

Task-bound exports add stable source identifiers, content digests, selected Skill identifiers, and a `ContextReceipt`. Receipt levels are deliberately narrow: `delivered` records transport, `acknowledged` records execution binding, and neither claims that a model understood or followed the context. EvolveTrace submission is optional and fail-open when the local evidence sink is unavailable; schema rejection remains an explicit error.

For a multi-repository task, prepare a reviewed contract before submitting it:

```bash
aictx task prepare example-api \
  --intent "Keep the API and UI contract aligned" \
  --platform codex \
  --contract examples/task-contract-v2.json

aictx task submit <task-id> \
  --evolvetrace-url http://127.0.0.1:8000
```

The v2 contract is validated before any task artifact is written. Repository paths must be workspace-relative, criterion IDs must be unique, and criterion configuration must match its type. The selected repositories are exported in one bounded Context Bundle, and the EvolveTrace client transports the constraints and criteria unchanged.

AI Context Kit authors, validates, and delivers this contract; it does not execute checks or claim that a criterion passed. EvolveTrace owns observable execution evidence, deterministic evaluation, and the human review decision. Existing task artifacts without `--contract` remain `task-envelope/v1` and retain their legacy submission behavior.

## Context ownership

Project files have two marked blocks. The CLI replaces only the automatic block:

```markdown
<!-- aictx:auto:start -->
Detected facts
<!-- aictx:auto:end -->

<!-- aictx:manual:start -->
Human or AI-maintained semantic memory
<!-- aictx:manual:end -->
```

Malformed markers are an error. An existing `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, or Cursor rule without the AI Context Kit marker is never overwritten.

## Privacy and limitations

Core discovery, rendering, and export stay offline and need no API key. The only networked CLI path is explicit `task submit`, restricted to loopback EvolveTrace URLs. The toolkit reads recognized manifests, a bounded README excerpt, Git metadata, directory names, and context sources explicitly allowlisted in `.aictx.toml`; it records digests and workspace-relative identifiers rather than copying unrestricted source archives. It does not follow directory symlinks or scan common secret files.

A `current` freshness label means the recorded observation inputs have not changed since the last render. Source code and behavior outside that scope still require direct inspection.

The local workflow remains deterministic and offline. Optional network access is isolated to the read-only MCP server, while model integration, vector search, background synchronization, and automatic business-level summaries remain outside the current release. The included Skill maintains the manual block and requires review before publication.

## Install the Codex Skill

Install the repository as a plugin, or copy/link `skills/manage-ai-context` into your Codex skills directory, then invoke `$manage-ai-context`. The Skill delegates deterministic work to the installed `aictx` command. The `aictx` Python package remains a separate runtime dependency.

## 中文快速开始

AI Context Kit 在本地维护一套 `.ai/` 共享上下文，让 Codex、Claude、Gemini 和 Cursor 不必反复分析同一批项目。它不会调用模型 API，也不会读取普通源代码正文。

完整说明见 [中文使用手册](docs/zh-CN/usage.md)；需要判断 CLI 和工作区是否健康时，使用 [中文自测手册](docs/zh-CN/self-check.md)。
判断上下文是否实际减少准备与纠正负担，使用[效果验证指南](docs/zh-CN/effectiveness.md)，分别核查交付、可观察使用和任务收益。

```powershell
pipx install "git+https://github.com/sorenjing/EvolveTrace.git@<published-commit-sha>#subdirectory=context"
aictx init --dry-run
aictx init
aictx status
```

项目变化后先运行 `aictx status`，再用 `aictx update <项目名> --dry-run` 审阅更新，确认后去掉 `--dry-run`。人工记忆只能写在 `manual` 标记区内，CLI 不会覆盖该区域。

私人资产包使用显式 Manifest 安装，不需要每次粘贴统一入口提示词：

```powershell
aictx setup --manifest personal-ai-pack.yaml
aictx install --manifest personal-ai-pack.yaml --target "$env:LOCALAPPDATA\aictx"
aictx doctor --target "$env:LOCALAPPDATA\aictx"
```

公开仓库只提供通用实现和合成示例；真实私人 Manifest 不应提交到本仓库。

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md). Security issues should follow [SECURITY.md](SECURITY.md).

## License

MIT

## Git repository context

`aictx repo inspect . --json` returns the repository root, branch (or detached
HEAD), commit, working-tree counts, upstream, and ahead/behind counts. The
upstream comparison uses only local cached refs; it does not check the live
remote. Use `--context-commit SHA` to assess a context entry created at that
commit. A changed HEAD or dirty working tree makes local context potentially
stale. A behind upstream ref makes remote freshness potentially stale without
invalidating local context. Missing commits, unavailable status, and absent
upstreams yield `unknown` rather than a false freshness claim.

When available, `ContextBundle v1` repository records include a Git source
with the repository, branch, commit, and workspace-relative path. The local
freshness comparison uses the commit saved when project context was last
updated. Existing `freshness` still describes the bounded observation
fingerprint; inspect source code directly when the task requires it.
