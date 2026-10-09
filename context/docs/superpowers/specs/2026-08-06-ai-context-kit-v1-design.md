# AI Context Kit v1 Design

## Purpose

Build an offline, cross-platform CLI and Codex Skill that maintain compact shared AI context across nested software projects. The tool must reduce repeated repository analysis without sending source code to a model or overwriting human-maintained memory.

## Scope

Version 1 supports Python 3.11 or newer on Windows, macOS, and Linux. It generates thin entry files for Codex, Claude, Gemini, and Cursor. It does not call model APIs, run a daemon, use a database, install editor extensions, or infer business semantics from source code.

## Repository and package

The repository is named `ai-context-kit`. The Python distribution is `ai-context-kit`, the import package is `ai_context_kit`, and the executable is `aictx`. The repository also contains a distributable Codex Skill named `manage-ai-context`.

## Workspace layout

`aictx init` creates the following managed structure in a selected workspace:

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

`GLOBAL.md` and `CURRENT.md` are human-owned templates. `WORKSPACE.md`, `state.json`, and automatic sections inside project memory files are tool-owned. AI entry files are created when absent and updated only when they still contain the tool's managed markers.

## Project discovery

The workspace root is the directory containing `.aictx.toml`, found by walking upward from the current directory. Initialization uses the explicitly supplied path or the current directory.

Project discovery walks below the workspace root and recognizes directories containing at least one marker from this set:

- `.git`
- `pyproject.toml`, `setup.py`, or `requirements.txt`
- `package.json`
- `Cargo.toml`
- `go.mod`
- `pom.xml` or `build.gradle`

The workspace root itself may be a project. Once a project is discovered, its descendants are not treated as separate projects unless they contain their own `.git` directory. Configuration can include or exclude paths and override discovered project names.

Default exclusions include dependency directories, virtual environments, caches, generated output, VCS internals, secrets, binary files, and files larger than 1 MiB.

## Fact extraction

The scanner reads only bounded metadata sources:

- recognized manifest files;
- the first heading and first non-empty paragraph of README files;
- Git branch, HEAD commit, and clean/dirty state;
- immediate and second-level directory names;
- declared scripts, entry points, and common build/test commands.

It does not read ordinary source file bodies. Extractors return a normalized `ProjectFacts` value so rendering is independent from discovery.

## State and staleness

`.ai/state.json` uses a versioned schema. For each project it records the normalized relative path, marker files, SHA-256 fingerprints of scanned metadata, and the fingerprint used for the most recent project-memory render.

`status` rescans fingerprints without writing and reports each project as `current`, `stale`, `new`, or `missing`. `scan` discovers projects and reports facts without modifying memory. `update` updates all stale projects or one named project. `init` performs initialization followed by the first update. `check` validates configuration, managed markers, state schema, and entry-file references.

## Managed content

Each `.ai/projects/<slug>.md` file contains exactly one automatic block and one manual block:

```markdown
<!-- aictx:auto:start -->
...
<!-- aictx:auto:end -->

<!-- aictx:manual:start -->
...
<!-- aictx:manual:end -->
```

The CLI replaces only the automatic block. It preserves the manual block byte-for-byte. Missing, duplicated, nested, or reversed markers are validation errors; the CLI must not repair them by overwriting content.

Generated files are deterministic: projects and facts are sorted, paths use `/`, timestamps are excluded from Markdown, and identical inputs produce identical bytes.

## Configuration

`.aictx.toml` uses Python's standard-library `tomllib`. Version 1 supports:

```toml
version = 1
max_file_bytes = 1048576

[discovery]
include = ["."]
exclude = [".git", ".ai", "node_modules", ".venv", "venv", "dist", "build", "target", "coverage"]

[projects]
# "projects/example" = "Example"
```

Unknown top-level keys produce a warning. Unsupported configuration versions or invalid value types are errors.

## CLI behavior

Commands use `argparse` and return stable exit codes:

- `0`: success and no validation problems;
- `1`: stale state or validation findings;
- `2`: usage, configuration, or unsafe-write error.

All commands support `--workspace PATH`. Mutating commands support `--dry-run`. Human-readable output is the v1 interface; machine-readable JSON output is deferred.

Writes use a temporary sibling followed by atomic replacement. Existing unrecognized entry files are never overwritten. A failed multi-file update may leave earlier atomic writes applied, but every individual file remains valid; rerunning the command converges to the desired state.

## AI adapters

Codex, Claude, Gemini, and Cursor entry files contain concise instructions to:

1. locate `.ai/GLOBAL.md` and `.ai/WORKSPACE.md`;
2. load only the selected project's memory file;
3. run `aictx status` before broad repository analysis;
4. update only the manual block when recording semantic memory;
5. avoid copying source code or conversation transcripts into memory.

All adapters reference the same `.ai` files and contain no duplicated project facts.

## Codex Skill

The `manage-ai-context` Skill instructs Codex to initialize, inspect, refresh, validate, and compact workspace memory with the CLI. Its `SKILL.md` remains concise and delegates deterministic operations to `aictx`. It includes `agents/openai.yaml` and is validated using the official skill validation script.

## Safety and privacy

The tool is offline and has no networking code. It never reads common secret files, including `.env`, private keys, credential stores, or files matched by configured exclusions. Paths are resolved and verified to remain inside the workspace before writes. Symlinked directories are not traversed. Existing user files are preserved unless they contain valid managed markers.

## Testing

Tests use `pytest` and temporary workspaces. Coverage includes:

- upward workspace discovery;
- nested project discovery and exclusions;
- manifest and README fact extraction;
- deterministic fingerprints and rendering;
- preservation of manual blocks;
- rejection of malformed markers and unsafe paths;
- dry-run behavior;
- CLI exit codes;
- adapters for all four AI tools;
- Windows-style and POSIX-style path normalization;
- installable package metadata and Skill validation.

GitHub Actions runs the suite on Windows, macOS, and Ubuntu with Python 3.11, 3.12, and 3.13.

## Documentation and release

The repository includes an English README with a concise Chinese quick start, an MIT license, contributing guidance, security policy, example workspace, and GitHub Actions. The initial release is version `0.1.0`. Publishing to PyPI is prepared but not performed in v1; GitHub publication occurs only after local verification and explicit review of repository visibility and ownership.

## Acceptance criteria

- Installing the package exposes a working `aictx` command.
- Initializing a temporary multi-project workspace creates all expected files.
- Re-running `update` without changes produces no file changes.
- Changing a recognized manifest makes only its project stale.
- Updating a stale project preserves its manual memory exactly.
- `check` detects damaged markers and never overwrites the affected file.
- No command requires network access or an API key.
- All automated tests and Skill validation pass locally.
