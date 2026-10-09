import json
from pathlib import Path

import pytest

from ai_context_kit.cli import main


def workspace(root: Path) -> Path:
    project = root / "projects" / "demo"
    project.mkdir(parents=True)
    (project / "pyproject.toml").write_text('[project]\nname="demo"\n', encoding="utf-8")
    assert main(["init", "--workspace", str(root)]) == 0
    (root / ".ai/GLOBAL.md").write_text("Shared preference", encoding="utf-8")
    memory = root / ".ai/projects/demo.md"
    memory.write_text(memory.read_text(encoding="utf-8").replace(
        "## Project memory", "## Project memory\n\nSelected decision"), encoding="utf-8")
    (root / ".ai/projects/unrelated.md").write_text("PRIVATE OTHER PROJECT", encoding="utf-8")
    return project


def load(root: Path, capsys, project: str | None = "demo") -> tuple[int, dict]:
    args = ["load", "--workspace", str(root), "--json"]
    if project:
        args.append(project)
    capsys.readouterr()
    code = main(args)
    return code, json.loads(capsys.readouterr().out)


def test_load_reads_only_selected_context_and_records_metadata(tmp_path, capsys):
    workspace(tmp_path)
    before = (tmp_path / ".ai/projects/demo.md").read_bytes()
    code, result = load(tmp_path, capsys)
    assert code == 0
    assert "Shared preference" in result["context"]
    assert "Selected decision" in result["context"]
    assert "PRIVATE OTHER PROJECT" not in result["context"]
    assert result["receipt"]["status"] == "returned"
    assert result["receipt"]["freshness"] == "current"
    assert result["receipt"]["model_use"] == "unknown"
    assert {source["path"] for source in result["receipt"]["sources"]} == {
        ".ai/GLOBAL.md", ".ai/WORKSPACE.md", ".ai/projects/demo.md"}
    raw = (tmp_path / ".ai/usage.json").read_text(encoding="utf-8")
    assert "Selected decision" not in raw
    assert str(tmp_path) not in raw
    assert (tmp_path / ".ai/projects/demo.md").read_bytes() == before


def test_usage_query_without_events_is_read_only(tmp_path, capsys):
    workspace(tmp_path)
    capsys.readouterr()
    assert main(["usage", "--workspace", str(tmp_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["events"] == []
    assert not (tmp_path / ".ai/usage.json").exists()


def test_usage_is_project_filtered_and_has_no_bodies(tmp_path, capsys):
    workspace(tmp_path)
    load(tmp_path, capsys)
    assert main(["usage", "demo", "--workspace", str(tmp_path), "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["events"][-1]["project"] == "demo"
    assert "context" not in result["events"][-1]
    assert main(["usage", "other", "--workspace", str(tmp_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["events"] == []


@pytest.mark.parametrize("problem", ["missing", "oversized", "markers"])
def test_incomplete_memory_is_explicit_and_not_silently_delivered(tmp_path, capsys, problem):
    workspace(tmp_path)
    memory = tmp_path / ".ai/projects/demo.md"
    if problem == "missing":
        memory.unlink()
    elif problem == "oversized":
        memory.write_text("X" * 100_000, encoding="utf-8")
    else:
        memory.write_text("unmarked decision", encoding="utf-8")
    code, result = load(tmp_path, capsys)
    assert code == 1
    assert result["receipt"]["status"] == "partial"
    assert result["receipt"]["findings"]
    assert ".ai/projects/demo.md" not in {s["path"] for s in result["receipt"]["sources"]}
    assert "X" * 1000 not in result["context"]
    assert "unmarked decision" not in result["context"]


def test_stale_source_is_flagged_without_automatic_update(tmp_path, capsys):
    project = workspace(tmp_path)
    before = (tmp_path / ".ai/projects/demo.md").read_bytes()
    (project / "pyproject.toml").write_text('[project]\nname="demo"\nversion="2"\n', encoding="utf-8")
    code, result = load(tmp_path, capsys)
    assert code == 1
    assert result["receipt"]["freshness"] == "stale"
    assert "stale" in result["context"]
    assert (tmp_path / ".ai/projects/demo.md").read_bytes() == before


def test_root_does_not_guess_project_and_unknown_project_does_not_load_others(tmp_path, capsys):
    workspace(tmp_path)
    code, result = load(tmp_path, capsys, None)
    assert code == 1
    assert result["receipt"]["project"] is None
    assert "project_required" in result["receipt"]["findings"]
    assert "Selected decision" not in result["context"]
    code, result = load(tmp_path, capsys, "unknown")
    assert code == 1
    assert "project_not_found" in result["receipt"]["findings"]
    assert "Selected decision" not in result["context"]


def test_receipt_retention_is_bounded(tmp_path, capsys):
    workspace(tmp_path)
    for _ in range(25):
        load(tmp_path, capsys)
    data = json.loads((tmp_path / ".ai/usage.json").read_text(encoding="utf-8"))
    assert len(data["events"]) == 20


def test_corrupt_usage_is_reported_not_overwritten(tmp_path, capsys):
    workspace(tmp_path)
    usage = tmp_path / ".ai/usage.json"
    usage.write_text("broken", encoding="utf-8")
    code, result = load(tmp_path, capsys)
    assert code == 1
    assert "usage_not_recorded" in result["receipt"]["findings"]
    assert usage.read_text(encoding="utf-8") == "broken"


def test_linked_memory_is_never_loaded(tmp_path, capsys):
    workspace(tmp_path)
    outside = tmp_path.parent / "outside-context.txt"
    outside.write_text("OUTSIDE SECRET", encoding="utf-8")
    memory = tmp_path / ".ai/GLOBAL.md"
    memory.unlink()
    try:
        memory.symlink_to(outside)
    except OSError:
        pytest.skip("symlink privilege unavailable")
    code, result = load(tmp_path, capsys)
    assert code == 1
    assert "OUTSIDE SECRET" not in result["context"]


def test_invalid_state_is_unknown_instead_of_crashing(tmp_path, capsys):
    workspace(tmp_path)
    (tmp_path / ".ai/state.json").write_text('{"version":1,"projects":{"demo":3}}', encoding="utf-8")
    code, result = load(tmp_path, capsys)
    assert code == 1
    assert result["receipt"]["freshness"] == "unknown"
    assert "freshness_unknown" in result["receipt"]["findings"]


def test_invalid_usage_schema_is_reported_by_query_without_traceback(tmp_path, capsys):
    workspace(tmp_path)
    (tmp_path / ".ai/usage.json").write_text('{"version":1,"events":[{"sources":[]}]}', encoding="utf-8")
    capsys.readouterr()
    assert main(["usage", "--workspace", str(tmp_path)]) == 2
    assert "error:" in capsys.readouterr().out


def test_cwd_matches_deepest_nested_git_project(tmp_path, capsys, monkeypatch):
    parent = workspace(tmp_path)
    nested = parent / "nested"
    (nested / ".git").mkdir(parents=True)
    (nested / "pyproject.toml").write_text('[project]\nname="nested"\n', encoding="utf-8")
    assert main(["update", "--workspace", str(tmp_path)]) == 0
    monkeypatch.chdir(nested)
    capsys.readouterr()
    assert main(["load", "--json"]) == 1  # Nested project's manual memory is still a template.
    result = json.loads(capsys.readouterr().out)
    assert result["receipt"]["project"] == "nested"
    assert ".ai/projects/demo.md" not in {s["path"] for s in result["receipt"]["sources"]}


def test_slug_collision_does_not_load_wrong_project(tmp_path, capsys):
    workspace(tmp_path)
    other = tmp_path / "projects" / "other"
    other.mkdir()
    (other / "pyproject.toml").write_text('[project]\nname="other"\n', encoding="utf-8")
    (tmp_path / ".aictx.toml").write_text('version=1\n[projects]\n"projects/other"="DEMO"\n', encoding="utf-8")
    code, result = load(tmp_path, capsys)
    assert code == 1
    assert "project_ambiguous" in result["receipt"]["findings"]
    assert "Selected decision" not in result["context"]


def test_default_manual_template_is_reported_as_a_context_gap(tmp_path, capsys):
    workspace(tmp_path)
    memory = tmp_path / ".ai/projects/demo.md"
    memory.write_text(memory.read_text(encoding="utf-8").replace("\nSelected decision", ""), encoding="utf-8")
    code, result = load(tmp_path, capsys)
    assert code == 1
    assert "semantic_memory_empty:.ai/projects/demo.md" in result["receipt"]["findings"]


def test_windows_reparse_memory_is_rejected_even_without_is_junction(tmp_path, capsys, monkeypatch):
    # Python 3.11 has no Path.is_junction: use the Windows lstat attribute as well.
    from types import SimpleNamespace
    workspace(tmp_path)
    original_lstat = Path.lstat
    monkeypatch.setattr(Path, "is_junction", lambda self: False, raising=False)

    def reparse_lstat(self):
        if self == tmp_path / ".ai/projects":
            # Path.is_symlink() also reads st_mode on Python 3.11-3.13.
            return SimpleNamespace(st_mode=original_lstat(self).st_mode,
                                   st_file_attributes=0x400)
        return original_lstat(self)

    monkeypatch.setattr(Path, "lstat", reparse_lstat)
    code, result = load(tmp_path, capsys)
    assert code == 1
    assert "Selected decision" not in result["context"]
