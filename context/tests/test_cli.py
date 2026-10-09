from pathlib import Path
import json
import shutil

import pytest

from ai_context_kit.cli import main
from test_personal_pack import valid_pack_v2, write_pack


def test_version_uses_package_version(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])

    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == "aictx 0.2.0"


def make_workspace(root: Path) -> None:
    project = root / "projects" / "demo"
    project.mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        '[project]\nname="demo"\n[project.scripts]\ntest="pytest"\n', encoding="utf-8"
    )
    (project / "README.md").write_text("# Demo\n\nExample project.\n", encoding="utf-8")


def test_init_creates_shared_context_and_is_idempotent(tmp_path: Path) -> None:
    make_workspace(tmp_path)

    assert main(["init", "--workspace", str(tmp_path)]) == 0
    first = (tmp_path / ".ai/projects/demo.md").read_bytes()
    assert main(["update", "--workspace", str(tmp_path)]) == 0

    assert (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / "GEMINI.md").exists()
    assert (tmp_path / ".cursor/rules/ai-context.mdc").exists()
    assert first == (tmp_path / ".ai/projects/demo.md").read_bytes()


def test_status_reports_stale_after_manifest_change(tmp_path: Path, capsys) -> None:
    make_workspace(tmp_path)
    assert main(["init", "--workspace", str(tmp_path)]) == 0
    manifest = tmp_path / "projects/demo/pyproject.toml"
    manifest.write_text(manifest.read_text(encoding="utf-8") + "version='2'\n", encoding="utf-8")

    assert main(["status", "--workspace", str(tmp_path)]) == 1

    assert "stale" in capsys.readouterr().out


def test_update_prunes_projects_removed_from_discovery(tmp_path: Path, capsys) -> None:
    make_workspace(tmp_path)
    assert main(["init", "--workspace", str(tmp_path)]) == 0

    shutil.rmtree(tmp_path / "projects" / "demo")

    assert main(["update", "--workspace", str(tmp_path)]) == 0
    assert main(["status", "--workspace", str(tmp_path)]) == 0
    assert "missing" not in capsys.readouterr().out


def test_dry_run_init_writes_nothing(tmp_path: Path) -> None:
    make_workspace(tmp_path)

    assert main(["init", "--workspace", str(tmp_path), "--dry-run"]) == 0

    assert not (tmp_path / ".aictx.toml").exists()
    assert not (tmp_path / ".ai").exists()


def test_check_rejects_damaged_project_markers(tmp_path: Path, capsys) -> None:
    make_workspace(tmp_path)
    assert main(["init", "--workspace", str(tmp_path)]) == 0
    memory = tmp_path / ".ai/projects/demo.md"
    memory.write_text(memory.read_text(encoding="utf-8").replace("<!-- aictx:manual:end -->", ""), encoding="utf-8")

    assert main(["check", "--workspace", str(tmp_path)]) == 1

    assert "marker" in capsys.readouterr().out.lower()


def test_scan_does_not_create_context_files(tmp_path: Path, capsys) -> None:
    make_workspace(tmp_path)
    (tmp_path / ".aictx.toml").write_text("version = 1\n", encoding="utf-8")

    assert main(["scan", "--workspace", str(tmp_path)]) == 0

    assert "demo" in capsys.readouterr().out
    assert not (tmp_path / ".ai").exists()


def test_update_preserves_manual_block_bytes_with_crlf(tmp_path: Path) -> None:
    make_workspace(tmp_path)
    assert main(["init", "--workspace", str(tmp_path)]) == 0
    memory = tmp_path / ".ai/projects/demo.md"
    contents = memory.read_bytes()
    start = contents.index(b"<!-- aictx:manual:start -->") + len(b"<!-- aictx:manual:start -->")
    end = contents.index(b"<!-- aictx:manual:end -->")
    manual = b"\r\n## Decisions\r\n\r\nKeep mixed newlines.\n\xe4\xb8\xad\xe6\x96\x87\r\n"
    memory.write_bytes(contents[:start] + manual + contents[end:])
    manifest = tmp_path / "projects/demo/pyproject.toml"
    manifest.write_text(manifest.read_text(encoding="utf-8") + "version='2'\n", encoding="utf-8")

    assert main(["update", "--workspace", str(tmp_path)]) == 0

    updated = memory.read_bytes()
    new_start = updated.index(b"<!-- aictx:manual:start -->") + len(b"<!-- aictx:manual:start -->")
    new_end = updated.index(b"<!-- aictx:manual:end -->")
    assert updated[new_start:new_end] == manual


def test_export_chatgpt_project_context_pack_includes_shared_and_project_context(
    tmp_path: Path, capsys
) -> None:
    make_workspace(tmp_path)
    assert main(["init", "--workspace", str(tmp_path)]) == 0
    (tmp_path / ".ai/GLOBAL.md").write_text(
        "# Global context\n\nUse concise Chinese by default.\n", encoding="utf-8"
    )
    memory = tmp_path / ".ai/projects/demo.md"
    memory.write_text(
        memory.read_text(encoding="utf-8").replace(
            "Record goals, architecture decisions, constraints, current state, and known issues here.",
            "Keep the public API offline-first.",
        ),
        encoding="utf-8",
    )

    assert main(["export", "chatgpt-project", "demo", "--workspace", str(tmp_path)]) == 0

    exported = tmp_path / ".ai/exports/demo-chatgpt-project.md"
    contents = exported.read_text(encoding="utf-8")
    assert "# ChatGPT Project Context: demo" in contents
    assert "Use concise Chinese by default." in contents
    assert "Keep the public API offline-first." in contents
    assert "https://learn.chatgpt.com/docs/projects" in contents
    assert "https://learn.chatgpt.com/docs/customization/memories" in contents
    assert "exported ChatGPT project context" in capsys.readouterr().out


@pytest.mark.parametrize("first,second", [("Same", "Same"), ("Foo Bar", "foo-bar")])
def test_init_rejects_project_name_or_slug_collisions_before_memory_writes(
    tmp_path: Path, first: str, second: str
) -> None:
    for path in ("projects/one", "projects/two"):
        project = tmp_path / path
        project.mkdir(parents=True)
        (project / ".git").mkdir()
    (tmp_path / ".aictx.toml").write_text(
        f'''version = 1
[projects]
"projects/one" = "{first}"
"projects/two" = "{second}"
''',
        encoding="utf-8",
    )

    assert main(["init", "--workspace", str(tmp_path)]) == 2

    assert not list((tmp_path / ".ai/projects").glob("*.md"))


@pytest.mark.parametrize("state", ["not json", '{"version": 99, "projects": {}}'])
def test_check_reports_invalid_state_schema(tmp_path: Path, state: str, capsys) -> None:
    make_workspace(tmp_path)
    assert main(["init", "--workspace", str(tmp_path)]) == 0
    (tmp_path / ".ai/state.json").write_text(state, encoding="utf-8")

    assert main(["check", "--workspace", str(tmp_path)]) == 1

    assert "state" in capsys.readouterr().out.lower()


def test_check_reports_modified_adapter_contents(tmp_path: Path, capsys) -> None:
    make_workspace(tmp_path)
    assert main(["init", "--workspace", str(tmp_path)]) == 0
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        agents.read_text(encoding="utf-8").replace(".ai/WORKSPACE.md", ".ai/MISSING.md"),
        encoding="utf-8",
    )

    assert main(["check", "--workspace", str(tmp_path)]) == 1

    assert "adapter" in capsys.readouterr().out.lower()


def test_locate_prints_stable_json_and_writes_nothing(tmp_path: Path, capsys) -> None:
    manifest = write_pack(tmp_path / "pack.json", valid_pack_v2())
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    portfolio = workspace / "private-portfolio"
    portfolio.mkdir()
    (portfolio / "registry.yaml").write_text("projects: {}\n", encoding="utf-8")
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    assert main(["locate", "--manifest", str(manifest), "--start", str(workspace), "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "resolved"
    assert payload["source"] == "discovery"
    assert payload["workspace_root"] == str(workspace)
    assert payload["portfolio_root"] == str(portfolio)
    assert payload["candidates"] == [str(portfolio)]
    assert payload["findings"] == []
    assert sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*")) == before
    assert not (tmp_path / ".aictx-pack").exists()


def test_locate_exit_codes_distinguish_unresolved_ambiguous_and_invalid(
    tmp_path: Path, capsys
) -> None:
    manifest = write_pack(tmp_path / "pack.json", valid_pack_v2())
    unresolved = tmp_path / "unresolved"
    unresolved.mkdir()
    (unresolved / ".aictx.toml").write_text("version = 1\n", encoding="utf-8")
    assert main(["locate", "--manifest", str(manifest), "--start", str(unresolved)]) == 1
    assert "unresolved" in capsys.readouterr().out

    ambiguous = tmp_path / "ambiguous"
    ambiguous.mkdir()
    for name in ("a", "b"):
        candidate = ambiguous / name / "private-portfolio"
        candidate.mkdir(parents=True)
        (candidate / "registry.yaml").write_text("projects: {}\n", encoding="utf-8")
    assert main(["locate", "--manifest", str(manifest), "--start", str(ambiguous)]) == 1
    assert "ambiguous" in capsys.readouterr().out

    assert main([
        "locate", "--manifest", str(manifest), "--start", str(tmp_path),
        "--portfolio", str(tmp_path / "missing"), "--json",
    ]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "invalid"


def test_task_prepare_prints_ids_and_relative_paths(tmp_path: Path, capsys) -> None:
    make_workspace(tmp_path)
    assert main(["init", "--workspace", str(tmp_path)]) == 0
    capsys.readouterr()

    assert main([
        "task", "prepare", "demo",
        "--intent", "Refresh project view",
        "--platform", "codex",
        "--skill", "public-content-safety",
        "--workspace", str(tmp_path),
    ]) == 0

    output = capsys.readouterr().out
    assert "Task ID:" in output
    assert "Bundle ID:" in output
    assert ".ai/tasks/" in output
    assert str(tmp_path) not in output


def test_task_prepare_accepts_reviewed_contract_file(tmp_path: Path) -> None:
    make_workspace(tmp_path)
    assert main(["init", "--workspace", str(tmp_path)]) == 0
    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps({"target_repositories":["projects/demo"],"constraints":[],"acceptance_criteria":[{"criterion_id":"tests","type":"command_exit_zero","required":True,"description":"Tests pass","config":{"command":"python -m pytest -q"}}]}), encoding="utf-8")
    assert main(["task","prepare","demo","--intent","Verify","--contract",str(contract),"--workspace",str(tmp_path)]) == 0
    envelope_path = next((tmp_path / ".ai/tasks").iterdir()) / "envelope.json"
    assert json.loads(envelope_path.read_text())["schema"] == "task-envelope/v2"


def test_task_submit_is_fail_open_when_evidence_sink_is_unavailable(
    tmp_path: Path, capsys
) -> None:
    make_workspace(tmp_path)
    assert main(["init", "--workspace", str(tmp_path)]) == 0
    capsys.readouterr()
    assert main([
        "task", "prepare", "demo",
        "--intent", "Refresh project view",
        "--platform", "codex",
        "--workspace", str(tmp_path),
    ]) == 0
    task_id = next((tmp_path / ".ai/tasks").iterdir()).name
    capsys.readouterr()

    assert main([
        "task", "submit", task_id,
        "--evolvetrace-url", "http://127.0.0.1:1",
        "--workspace", str(tmp_path),
    ]) == 0

    assert "observability incomplete" in capsys.readouterr().out


def test_publish_github_creates_commit_ready_directory(tmp_path: Path, capsys) -> None:
    make_workspace(tmp_path)
    assert main(["init", "--workspace", str(tmp_path)]) == 0
    capsys.readouterr()

    assert main(["publish", "github", "demo", "--workspace", str(tmp_path)]) == 0

    assert (tmp_path / ".ai/published/index.json").exists()
    assert (tmp_path / ".ai/published/projects/demo.json").exists()
    assert "review and commit" in capsys.readouterr().out


def test_pack_lifecycle_commands_require_explicit_manifest_and_target(
    tmp_path: Path, capsys
) -> None:
    from test_personal_pack import valid_pack, write_pack

    manifest = write_pack(tmp_path / "pack.json", valid_pack())
    target = tmp_path / "installed"

    assert main(["setup", "--manifest", str(manifest)]) == 0
    assert "valid" in capsys.readouterr().out
    assert main(["install", "--manifest", str(manifest), "--target", str(target)]) == 0
    assert main(["status", "--pack-target", str(target)]) == 0
    output = capsys.readouterr().out
    assert "example-personal-ai" in output
    assert str(tmp_path) not in output
    assert main(["doctor", "--target", str(target)]) == 0

    plugin = target / ".aictx-pack/generated/openai/plugin.json"
    original_plugin = plugin.read_bytes()
    plugin.write_text("{}\n", encoding="utf-8")
    assert main(["doctor", "--target", str(target)]) == 1
    assert "digest mismatch" in capsys.readouterr().out

    assert main([
        "update", "--manifest", str(manifest), "--target", str(target)
    ]) == 2
    assert "modified managed pack files" in capsys.readouterr().out
    plugin.write_bytes(original_plugin)
    assert main([
        "update", "--manifest", str(manifest), "--target", str(target)
    ]) == 0
    assert main(["uninstall", "--target", str(target)]) == 0
    assert not (target / ".aictx-pack").exists()
