from datetime import datetime, timezone
import json
from pathlib import Path

from ai_context_kit.publish import publish_bundle

from test_cli import make_workspace
from ai_context_kit.cli import main


def test_publish_bundle_writes_reviewable_bundle_and_index(tmp_path: Path) -> None:
    make_workspace(tmp_path)
    assert main(["init", "--workspace", str(tmp_path)]) == 0
    destination = tmp_path / "published"

    result = publish_bundle(
        tmp_path,
        "demo",
        destination,
        generated_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
    )

    assert result == destination / "projects/demo.json"
    bundle = json.loads(result.read_text(encoding="utf-8"))
    index = json.loads((destination / "index.json").read_text(encoding="utf-8"))
    assert bundle["schema_version"] == "context-bundle/v1"
    assert index == {
        "schema_version": "context-bundle-index/v1",
        "projects": [
            {
                "generated_at": "2026-09-11T00:00:00+00:00",
                "path": "projects/demo.json",
                "project": "demo",
                "schema_version": "context-bundle/v1",
            }
        ],
    }


def test_publish_preserves_other_projects_and_replaces_same_project(tmp_path: Path) -> None:
    make_workspace(tmp_path)
    assert main(["init", "--workspace", str(tmp_path)]) == 0
    destination = tmp_path / "published"
    destination.mkdir()
    (destination / "index.json").write_text(
        json.dumps(
            {
                "schema_version": "context-bundle-index/v1",
                "projects": [
                    {
                        "project": "other",
                        "path": "projects/other.json",
                        "schema_version": "context-bundle/v1",
                        "generated_at": "2026-09-01T00:00:00+00:00",
                    },
                    {
                        "project": "demo",
                        "path": "projects/demo.json",
                        "schema_version": "context-bundle/v1",
                        "generated_at": "2026-09-02T00:00:00+00:00",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    publish_bundle(tmp_path, "demo", destination)

    index = json.loads((destination / "index.json").read_text(encoding="utf-8"))
    assert [item["project"] for item in index["projects"]] == ["demo", "other"]

