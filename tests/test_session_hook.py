import json
from pathlib import Path
import subprocess
import sys


HOOK = Path(__file__).parents[1] / "hooks" / "session_start.py"


def run_hook(cwd: Path) -> dict[str, object] | None:
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"cwd": str(cwd), "hook_event_name": "SessionStart", "source": "startup"}),
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    return json.loads(result.stdout) if result.stdout else None


def test_prompts_workspace_loading_without_injecting_memory(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    selected = root / "projects" / "demo" / "src"
    selected.mkdir(parents=True)
    (root / ".aictx.toml").write_text("version = 1\n", encoding="utf-8")
    memory = root / ".ai" / "projects"
    memory.mkdir(parents=True)
    (root / ".ai/GLOBAL.md").write_text("Shared preference", encoding="utf-8")
    (root / ".ai/WORKSPACE.md").write_text(
        "# Workspace\n- [demo](projects/demo.md) — `projects/demo`\n"
        "- [other](projects/other.md) — `projects/other`\n",
        encoding="utf-8",
    )
    (memory / "demo.md").write_text("Selected decision", encoding="utf-8")
    (memory / "other.md").write_text("Private other project", encoding="utf-8")

    output = run_hook(selected)

    context = output["hookSpecificOutput"]["additionalContext"]
    assert "nearest ancestor" in context
    assert "manage-ai-context" in context
    assert "Shared preference" not in context
    assert "Selected decision" not in context
    assert "Private other project" not in context


def test_missing_directory_returns_no_context(tmp_path: Path) -> None:
    assert run_hook(tmp_path / 'missing') is None


def test_oversized_memory_is_not_injected(tmp_path: Path) -> None:
    (tmp_path / ".aictx.toml").write_text("version = 1\n", encoding="utf-8")
    memory = tmp_path / ".ai"
    memory.mkdir()
    (memory / "GLOBAL.md").write_text("X" * 100_000, encoding="utf-8")
    (memory / "WORKSPACE.md").write_text("# Workspace", encoding="utf-8")

    output = run_hook(tmp_path)

    assert "X" * 1000 not in output["hookSpecificOutput"]["additionalContext"]
