from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest

from ai_context_kit.cli import main
from ai_context_kit.config import ConfigError
from ai_context_kit.harness_export import build_harness_bundle
from ai_context_kit.task_contracts import TaskEnvelope

from test_cli import make_workspace


def test_build_harness_bundle_uses_v1_schema_and_workspace_relative_paths(tmp_path: Path) -> None:
    make_workspace(tmp_path)
    assert main(["init", "--workspace", str(tmp_path)]) == 0

    bundle = build_harness_bundle(
        tmp_path,
        "demo",
        generated_at=datetime(2026, 9, 9, tzinfo=timezone.utc),
    )

    assert bundle["schema_version"] == "context-bundle/v1"
    assert bundle["project"] == "demo"
    assert bundle["generated_at"] == "2026-09-09T00:00:00+00:00"
    assert bundle["freshness"] == "current"
    assert bundle["repositories"] == [{"name": "demo", "relative_path": "projects/demo"}]
    assert str(tmp_path) not in json.dumps(bundle)


def test_export_harness_writes_json_to_stdout_without_mutating_workspace(
    tmp_path: Path, capsys
) -> None:
    make_workspace(tmp_path)
    assert main(["init", "--workspace", str(tmp_path)]) == 0
    capsys.readouterr()
    before = (tmp_path / ".ai/state.json").read_bytes()

    assert (
        main(
            [
                "export",
                "harness",
                "demo",
                "--format",
                "json",
                "--output",
                "-",
                "--workspace",
                str(tmp_path),
            ]
        )
        == 0
    )

    bundle = json.loads(capsys.readouterr().out)
    assert bundle["schema_version"] == "context-bundle/v1"
    assert bundle["project"] == "demo"
    assert (tmp_path / ".ai/state.json").read_bytes() == before


def test_task_bound_bundle_adds_stable_source_records_without_changing_v1_schema(
    tmp_path: Path,
) -> None:
    make_workspace(tmp_path)
    assert main(["init", "--workspace", str(tmp_path)]) == 0
    source = tmp_path / "portfolio" / "content-workbench.md"
    source.parent.mkdir()
    source.write_text("# Content Workbench\n\nTracing is implemented.\n", encoding="utf-8")
    config = tmp_path / ".aictx.toml"
    config.write_text(
        config.read_text(encoding="utf-8")
        + '\n[context_sources]\ndemo = ["portfolio/content-workbench.md"]\n',
        encoding="utf-8",
    )
    task = TaskEnvelope.create(
        task_id="task-123",
        target_project="demo",
        intent="Refresh a generated project view",
        requested_by="human",
        platform="codex",
        created_at=datetime(2026, 9, 16, tzinfo=timezone.utc),
    )

    bundle = build_harness_bundle(
        tmp_path,
        "demo",
        task=task,
        skill_ids=("public-content-safety",),
        generated_at=datetime(2026, 9, 16, tzinfo=timezone.utc),
    )

    assert bundle["schema_version"] == "context-bundle/v1"
    assert bundle["task"] == {"task_id": "task-123"}
    assert bundle["bundle_id"].startswith("ctx_")
    assert len(bundle["content_digest"]) == 64
    assert bundle["sources"][1:] == [
        {
            "source_id": "project:demo:portfolio/content-workbench.md",
            "relative_path": "portfolio/content-workbench.md",
            "content_digest": hashlib.sha256(source.read_bytes()).hexdigest(),
            "authority": "project",
        }
    ]
    assert bundle["skill_ids"] == ["public-content-safety"]
    assert str(tmp_path) not in json.dumps(bundle)


def test_context_source_must_stay_inside_workspace(tmp_path: Path) -> None:
    make_workspace(tmp_path)
    assert main(["init", "--workspace", str(tmp_path)]) == 0
    config = tmp_path / ".aictx.toml"
    config.write_text(
        config.read_text(encoding="utf-8")
        + '\n[context_sources]\ndemo = ["../private.md"]\n',
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="workspace-relative"):
        build_harness_bundle(tmp_path, "demo")


def test_task_bundle_can_include_two_target_repositories(tmp_path: Path) -> None:
    make_workspace(tmp_path)
    other = tmp_path / "projects" / "other"
    other.mkdir()
    (other / ".git").mkdir()
    (other / "pyproject.toml").write_text('[project]\nname = "other"\n')
    assert main(["init", "--workspace", str(tmp_path)]) == 0
    bundle = build_harness_bundle(tmp_path, "demo", repository_paths=("projects/demo", "projects/other"))
    assert [item["relative_path"] for item in bundle["repositories"]] == ["projects/demo", "projects/other"]
    assert "related_projects" in bundle["context"]
