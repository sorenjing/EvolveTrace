# AI Context Kit v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an installable offline CLI and Codex Skill that incrementally maintains shared project context for Codex, Claude, Gemini, and Cursor.

**Architecture:** Keep scanning, fact extraction, state comparison, managed-block rendering, and CLI orchestration in focused Python modules. Store deterministic Markdown plus a versioned JSON fingerprint cache in each initialized workspace; keep semantic memory in byte-preserved manual blocks.

**Tech Stack:** Python 3.11+, standard library runtime, pytest development tests, Hatchling build backend, GitHub Actions.

## Global Constraints

- Support Python 3.11 or newer on Windows, macOS, and Linux.
- Make no network calls and require no API key.
- Read bounded metadata sources, not ordinary source file bodies.
- Never follow symlinked directories or write outside the resolved workspace.
- Preserve manual blocks byte-for-byte and refuse malformed managed markers.
- Generate deterministic Markdown with `/` path separators.
- Support Codex, Claude, Gemini, and Cursor entry files.

---

### Task 1: Package skeleton and configuration

**Files:**
- Create: `pyproject.toml`
- Create: `src/ai_context_kit/__init__.py`
- Create: `src/ai_context_kit/config.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Produces: `Config`, `ConfigError`, `find_workspace(start: Path) -> Path`, and `load_config(root: Path) -> Config`.

- [ ] Write tests that prove upward workspace discovery, default values, valid TOML parsing, invalid versions, and invalid value types.
- [ ] Run `python -m pytest tests/test_config.py -v` and confirm import/behavior failures.
- [ ] Implement immutable configuration values using `dataclasses`, `tomllib`, and resolved workspace paths.
- [ ] Run the focused tests and confirm they pass.
- [ ] Commit with `feat: add package configuration`.

Representative contract:

```python
@dataclass(frozen=True)
class Config:
    root: Path
    max_file_bytes: int
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    project_names: dict[str, str]
```

### Task 2: Project discovery and offline fact extraction

**Files:**
- Create: `src/ai_context_kit/models.py`
- Create: `src/ai_context_kit/discovery.py`
- Create: `src/ai_context_kit/facts.py`
- Create: `tests/test_discovery.py`
- Create: `tests/test_facts.py`

**Interfaces:**
- Consumes: `Config` from Task 1.
- Produces: `Project`, `ProjectFacts`, `discover_projects(config: Config) -> list[Project]`, and `extract_facts(project: Project, config: Config) -> ProjectFacts`.

- [ ] Write discovery tests for root projects, nested repositories, nested package markers, exclusions, and symlink avoidance.
- [ ] Run the discovery tests and confirm failures.
- [ ] Implement deterministic discovery with explicit marker and exclusion constants.
- [ ] Write extraction tests for Python, Node, Cargo, Go, README excerpts, Git metadata, commands, and bounded directory trees.
- [ ] Run extraction tests and confirm failures.
- [ ] Implement manifest-specific standard-library parsers and safe subprocess calls to Git.
- [ ] Run both focused test files and confirm they pass.
- [ ] Commit with `feat: discover projects and extract facts`.

Representative contract:

```python
@dataclass(frozen=True)
class ProjectFacts:
    project: Project
    description: str | None
    technologies: tuple[str, ...]
    commands: tuple[tuple[str, str], ...]
    directories: tuple[str, ...]
    git_branch: str | None
    git_head: str | None
    git_dirty: bool | None
    scanned_files: tuple[Path, ...]
```

### Task 3: Fingerprints, state, and staleness

**Files:**
- Create: `src/ai_context_kit/state.py`
- Create: `tests/test_state.py`

**Interfaces:**
- Consumes: `ProjectFacts`.
- Produces: `WorkspaceState`, `ProjectState`, `fingerprint_facts(facts: ProjectFacts) -> str`, `load_state(root: Path) -> WorkspaceState`, `classify_projects(...) -> dict[str, str]`, and `write_state(...)`.

- [ ] Write tests for stable SHA-256 fingerprints, versioned JSON, missing state, changed manifests, new projects, and missing projects.
- [ ] Run the focused tests and confirm failures.
- [ ] Implement sorted JSON serialization and atomic sibling-file replacement.
- [ ] Run the focused tests and confirm they pass.
- [ ] Commit with `feat: track project context staleness`.

### Task 4: Managed Markdown and AI adapters

**Files:**
- Create: `src/ai_context_kit/render.py`
- Create: `src/ai_context_kit/adapters.py`
- Create: `tests/test_render.py`
- Create: `tests/test_adapters.py`

**Interfaces:**
- Consumes: `ProjectFacts`.
- Produces: `MarkerError`, `render_project_memory(facts, existing: str | None) -> str`, `render_workspace(facts) -> str`, `render_adapters() -> dict[Path, str]`, and `write_managed_file(...)`.

- [ ] Write tests proving deterministic rendering and exact manual-block preservation.
- [ ] Add malformed-marker cases for missing, repeated, reversed, and nested markers.
- [ ] Run render tests and confirm failures.
- [ ] Implement strict marker parsing and automatic-block rendering.
- [ ] Write adapter tests for `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, and `.cursor/rules/ai-context.mdc`, including refusal to overwrite unrecognized files.
- [ ] Implement thin managed adapters with common `.ai` references.
- [ ] Run both focused test files and confirm they pass.
- [ ] Commit with `feat: render shared context and ai adapters`.

### Task 5: CLI workflows

**Files:**
- Create: `src/ai_context_kit/cli.py`
- Create: `src/ai_context_kit/__main__.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: all prior public functions.
- Produces: `main(argv: Sequence[str] | None = None) -> int` and installed `aictx` command.

- [ ] Write end-to-end temporary-workspace tests for `init`, `scan`, `status`, `update`, `check`, `--workspace`, and `--dry-run`.
- [ ] Assert exit codes 0, 1, and 2 for success, findings, and invalid operations.
- [ ] Run CLI tests and confirm failures.
- [ ] Implement `argparse` subcommands and orchestration without duplicating scanner or renderer logic.
- [ ] Run CLI tests and confirm they pass.
- [ ] Install editable package and manually run `aictx --help` plus an init/status/update cycle in a temporary directory.
- [ ] Commit with `feat: add aictx command workflows`.

### Task 6: Codex Skill

**Files:**
- Create: `skill/manage-ai-context/SKILL.md`
- Create: `skill/manage-ai-context/agents/openai.yaml`
- Create: `tests/test_skill.py`

**Interfaces:**
- Consumes: installed `aictx` CLI behavior.
- Produces: a valid distributable Skill named `manage-ai-context`.

- [ ] Initialize the Skill with the official `init_skill.py` generator and no unnecessary resource directories.
- [ ] Write a test that asserts the Skill frontmatter, CLI command references, and absence of placeholder text.
- [ ] Run the focused test and confirm any template failure.
- [ ] Replace the generated instructions with the concise initialize/load/refresh/compact workflow and generate matching `agents/openai.yaml`.
- [ ] Run `quick_validate.py skill/manage-ai-context` and the focused test.
- [ ] Commit with `feat: add manage-ai-context codex skill`.

### Task 7: Documentation, examples, and release automation

**Files:**
- Create: `README.md`
- Create: `LICENSE`
- Create: `CONTRIBUTING.md`
- Create: `SECURITY.md`
- Create: `.gitignore`
- Create: `.github/workflows/ci.yml`
- Create: `examples/workspace/.aictx.toml`
- Create: `examples/workspace/README.md`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: the completed CLI and Skill.
- Produces: an installable `0.1.0` source/wheel distribution and a contributor-ready GitHub repository.

- [ ] Document installation, five commands, managed-block ownership, privacy behavior, supported AI tools, Chinese quick start, and limitations.
- [ ] Add an MIT license, contribution/test instructions, private vulnerability reporting instructions, and focused ignore rules.
- [ ] Add a minimal example workspace and CI matrix for Python 3.11, 3.12, and 3.13 on Windows, macOS, and Ubuntu.
- [ ] Run the full test suite and package build; inspect wheel contents for the Python package and Skill files.
- [ ] Run `aictx init`, repeated `update`, changed-manifest `status`, and malformed-marker `check` acceptance scenarios.
- [ ] Commit with `docs: prepare ai-context-kit v0.1.0`.

### Task 8: Final verification and GitHub publication

**Files:**
- Modify only files required by verification findings.

**Interfaces:**
- Consumes: the verified local repository.
- Produces: a clean main branch ready for a public GitHub repository.

- [ ] Run `python -m pytest -q` from a clean environment.
- [ ] Run package build and Skill validation again.
- [ ] Inspect `git status`, tracked files, and commit history for secrets or unrelated artifacts.
- [ ] Confirm the desired GitHub owner, repository name, public visibility, and description before external creation.
- [ ] Create the GitHub repository, add the remote, and push `main` only after that confirmation.
