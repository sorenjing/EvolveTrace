import json
from pathlib import Path
import subprocess
import sys
import os

from ai_context_kit.cli import main


HOOK = Path(__file__).parents[1] / "hooks" / "session_start.py"


def run_hook(cwd: Path) -> dict[str, object] | None:
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"cwd": str(cwd), "hook_event_name": "SessionStart", "source": "startup"}),
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
        env={**os.environ, "PYTHONPATH": str(HOOK.parent.parent / "src")},
    )
    return json.loads(result.stdout) if result.stdout else None


def test_loads_selected_context_and_records_hook_receipt(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    selected = root / "projects" / "demo" / "src"
    selected.mkdir(parents=True)
    (selected.parent / "pyproject.toml").write_text('[project]\nname="demo"\n', encoding="utf-8")
    assert main(["init", "--workspace", str(root)]) == 0
    memory = root / ".ai" / "projects"
    (root / ".ai/GLOBAL.md").write_text("Shared preference", encoding="utf-8")
    (root / ".ai/WORKSPACE.md").write_text(
        "# Workspace\n- [demo](projects/demo.md) — `projects/demo`\n"
        "- [other](projects/other.md) — `projects/other`\n",
        encoding="utf-8",
    )
    demo_memory = memory / "demo.md"
    demo_memory.write_text(demo_memory.read_text(encoding="utf-8").replace(
        "## Project memory", "## Project memory\nSelected decision"), encoding="utf-8")
    (memory / "other.md").write_text("Private other project", encoding="utf-8")

    output = run_hook(selected)

    context = output["hookSpecificOutput"]["additionalContext"]
    assert "Shared preference" in context
    assert "Selected decision" in context
    assert "Private other project" not in context
    assert "AI Context Kit" in output["systemMessage"]
    receipt = json.loads((root / ".ai/usage.json").read_text(encoding="utf-8"))["events"][-1]
    assert receipt["trigger"] == "SessionStart:startup"
    assert receipt["status"] == "returned"


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


def test_missing_cli_is_visible_and_does_not_inject_context(tmp_path):
    result = subprocess.run([sys.executable, "-I", "-S", str(HOOK)],
                            input='{}', text=True, capture_output=True, check=True,
                            env={**os.environ, "PATH": "", "PYTHONPATH": ""})
    output = json.loads(result.stdout)
    assert "CLI unavailable" in output["systemMessage"]
    assert "hookSpecificOutput" not in output


def test_session_identifier_is_hashed_and_invalid_event_is_ignored(tmp_path):
    (tmp_path / ".aictx.toml").write_text("version=1\n", encoding="utf-8")
    result = subprocess.run([sys.executable, str(HOOK)],
                            input=json.dumps({"cwd": str(tmp_path), "session_id": "private-session-id", "source": "resume"}),
                            text=True, capture_output=True, check=True,
                            env={**os.environ, "PYTHONPATH": str(HOOK.parent.parent / "src")})
    assert json.loads(result.stdout)["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    receipt = (tmp_path / ".ai/usage.json").read_text(encoding="utf-8")
    assert "private-session-id" not in receipt
    assert "session_sha256" in receipt
    bad = subprocess.run([sys.executable, str(HOOK)], input='not-json', text=True,
                         capture_output=True, check=True,
                         env={**os.environ, "PYTHONPATH": str(HOOK.parent.parent / "src")})
    assert bad.stdout == ""


def test_old_cli_failure_is_visible_without_leaking_stderr(monkeypatch, capsys):
    import builtins
    import io
    import runpy

    adapter = runpy.run_path(str(HOOK))
    original_import = builtins.__import__

    def unavailable(name, *args, **kwargs):
        if name == "ai_context_kit.context_delivery":
            raise ImportError("not installed in this interpreter")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", unavailable)
    monkeypatch.setattr(adapter["shutil"], "which", lambda _: "aictx")
    monkeypatch.setattr(adapter["subprocess"], "run", lambda *a, **kw:
                        subprocess.CompletedProcess([], 2, "", "private error details"))
    monkeypatch.setattr(sys, "stdin", io.StringIO('{}'))
    adapter["main"]()
    output = capsys.readouterr().out
    assert "CLI failed" in json.loads(output)["systemMessage"]
    assert "private error details" not in output
