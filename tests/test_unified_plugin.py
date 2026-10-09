"""Exercise the installed plugin payload, rather than only its configuration."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]


def builder():
    spec = importlib.util.spec_from_file_location("unified_plugin_builder", ROOT / "scripts/build_plugin_archive.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extracted_plugin_resolves_all_hooks_and_loads_context(tmp_path: Path):
    build = builder()
    archive = build.build_archive(ROOT, tmp_path / "plugin.zip")
    extracted = tmp_path / "plugin with spaces"
    with zipfile.ZipFile(archive) as package:
        package.extractall(extracted)
        names = package.namelist()
    assert not any(".git/" in name or ".ai/" in name or "venv/" in name for name in names)
    assert "LICENSE" in names and "context/LICENSE" in names and "NOTICE" in names
    manifest = json.loads((extracted / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "evolvetrace"
    assert (extracted / manifest["skills"] / "manage-ai-context/SKILL.md").is_file()
    hooks = json.loads((extracted / "hooks/hooks.json").read_text(encoding="utf-8"))["hooks"]
    startup = hooks["SessionStart"]
    assert len(startup) == 2
    for entries in hooks.values():
        for entry in entries:
            for hook in entry["hooks"]:
                command = hook["command"]
                assert command.startswith('python "${PLUGIN_ROOT}/') and command.endswith('"')
                relative = command.removeprefix('python "${PLUGIN_ROOT}/').removesuffix('"')
                assert (extracted / relative).is_file()
    workspace = tmp_path / "workspace"
    project = workspace / "example-app"
    project.mkdir(parents=True)
    (project / "package.json").write_text('{"name":"example-app"}', encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(ROOT / "context/src")}
    subprocess.run([sys.executable, "-m", "ai_context_kit", "init", "--workspace", str(workspace)], env=env, check=True, capture_output=True)
    memory = workspace / ".ai/projects/example-app.md"
    memory.write_text(memory.read_text(encoding="utf-8").replace("## Project memory", "## Project memory\n\n- Current product name: Example App."), encoding="utf-8")
    result = subprocess.run([sys.executable, str(extracted / "context/hooks/session_start.py")],
                            input=json.dumps({"hook_event_name":"SessionStart", "cwd":str(project)}),
                            env=env, text=True, capture_output=True, check=True)
    payload = json.loads(result.stdout)
    assert "Current product name: Example App" in payload["hookSpecificOutput"]["additionalContext"]
    usage = json.loads((workspace / ".ai/usage.json").read_text(encoding="utf-8"))
    assert len(usage["events"]) == 1


def test_archive_ignores_runtime_data_and_rejects_required_links(tmp_path: Path):
    build = builder()
    fake = tmp_path / "source"
    for relative in build.PAYLOAD_FILES:
        target = fake / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    skill = fake / "context/skills/manage-ai-context"
    (skill / "__pycache__").mkdir()
    (skill / "__pycache__/private.pyc").write_bytes(b"not a plugin file")
    (fake / ".ai").mkdir()
    (fake / ".ai/private.md").write_text("do not ship", encoding="utf-8")
    with zipfile.ZipFile(build.build_archive(fake, tmp_path / "safe.zip")) as archive:
        assert not any("__pycache__" in name or "private.md" in name for name in archive.namelist())
    required = fake / "context/hooks/session_start.py"
    required.unlink()
    try:
        required.symlink_to(ROOT / "context/hooks/session_start.py")
    except OSError:
        pytest.skip("symlink creation requires Windows privileges")
    with pytest.raises(ValueError, match="link"):
        build.build_archive(fake, tmp_path / "unsafe.zip")


def test_archive_refuses_output_inside_canonical_skill(tmp_path: Path):
    build = builder()
    with pytest.raises(ValueError, match="outside"):
        build.build_archive(ROOT, ROOT / "context/skills/manage-ai-context/generated.zip")
