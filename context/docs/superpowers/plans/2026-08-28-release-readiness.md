# AI Context Kit Release Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add verifiable version reporting and prepare a safe, documented PyPI release path without publishing.

**Architecture:** Keep `src/ai_context_kit/__init__.py` as the version source and configure Hatchling to read it dynamically. Expose the same value through argparse, then add tag-gated build, wheel smoke-test and Trusted Publishing automation.

**Tech Stack:** Python 3.11+, argparse, Hatchling, pytest, GitHub Actions, PyPI Trusted Publishing

**Spec:** `docs/superpowers/specs/2026-08-28-release-readiness-design.md`

## Global Constraints

- Preserve all existing commands and exit codes.
- Keep the runtime standard-library only.
- Do not create a tag, GitHub Release or PyPI release.
- The release workflow must fail before upload if build or wheel smoke tests fail.

---

### Task 1: Expose a single-source CLI version

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `src/ai_context_kit/cli.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: `ai_context_kit.__version__: str`
- Produces: `aictx --version` and dynamic Hatchling package metadata

- [ ] **Step 1: Write the failing CLI version test**

```python
def test_version_uses_package_version(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == "aictx 0.1.0"
```

- [ ] **Step 2: Run the test and confirm argparse rejects `--version`**

Run: `python -m pytest tests/test_cli.py::test_version_uses_package_version -q`

- [ ] **Step 3: Add argparse version handling**

Import `__version__` from the package and add `parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")` before subparser creation.

- [ ] **Step 4: Configure dynamic package metadata**

Replace the static project version with `dynamic = ["version"]` and add:

```toml
[tool.hatch.version]
path = "src/ai_context_kit/__init__.py"
```

- [ ] **Step 5: Run all tests and build metadata checks**

Run: `python -m pytest -q`
Run: `python -m build`

- [ ] **Step 6: Commit**

```text
feat: expose package version
```

### Task 2: Add release documentation and accurate install instructions

**Files:**
- Create: `CHANGELOG.md`
- Create: `docs/releasing.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: version `0.1.0` and current GitHub repository URL
- Produces: a release checklist and truthful pre-PyPI installation path

- [ ] **Step 1: Document 0.1.0 without claiming publication**

List the shipped CLI commands, safety boundaries, cross-platform CI and known v1 omissions in `CHANGELOG.md`.

- [ ] **Step 2: Add the release checklist**

Require clean Git status, full tests, build, isolated wheel installation, `aictx --version`, GitHub Environment setup, PyPI Trusted Publisher setup, then tag creation.

- [ ] **Step 3: Correct README installation commands**

Label PyPI installation as available only after the first release. Until then document `pipx install git+https://github.com/sorenjing/ai-context-kit.git`.

- [ ] **Step 4: Commit**

```text
docs: add release checklist
```

### Task 3: Add a tag-gated release workflow

**Files:**
- Create: `.github/workflows/release.yml`

**Interfaces:**
- Consumes: tags matching `v*`, the `pypi` GitHub Environment, PyPI Trusted Publishing
- Produces: verified sdist/wheel artifacts and a PyPI upload job

- [ ] **Step 1: Add build and smoke-test job**

Use Python 3.12, install `build`, run `python -m build`, create a clean virtual environment, install the generated wheel, and run `aictx --version`.

- [ ] **Step 2: Add upload job with least privilege**

Depend on the build job, download its artifact, set `environment: pypi`, grant only `id-token: write`, and use `pypa/gh-action-pypi-publish@release/v1`.

- [ ] **Step 3: Validate without publishing**

Build locally, install the wheel into a temporary virtual environment, run `aictx --version`, inspect workflow permissions, and run `git diff --check`.

- [ ] **Step 4: Commit**

```text
ci: prepare trusted package publishing
```

