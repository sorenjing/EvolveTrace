from pathlib import Path
import json

import pytest

from ai_context_kit.models import Project, ProjectFacts
from ai_context_kit.state import (
    ProjectState,
    StateError,
    WorkspaceState,
    classify_projects,
    fingerprint_facts,
    load_state,
    write_state,
)


def facts_at(root: Path) -> ProjectFacts:
    manifest = root / "pyproject.toml"
    return ProjectFacts(
        Project("demo", root, ".", ("pyproject.toml",)),
        None,
        ("Python",),
        (),
        (),
        None,
        None,
        None,
        (manifest.relative_to(root),),
    )


def test_fingerprint_changes_with_manifest_contents(tmp_path: Path) -> None:
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text("version='1'", encoding="utf-8")
    facts = facts_at(tmp_path)
    first = fingerprint_facts(facts)

    manifest.write_text("version='2'", encoding="utf-8")

    assert fingerprint_facts(facts) != first


def test_state_round_trips_as_versioned_json(tmp_path: Path) -> None:
    state = WorkspaceState({"demo": ProjectState(".", "abc", "abc")})

    write_state(tmp_path, state)

    assert load_state(tmp_path) == state


def test_classifies_new_current_stale_and_missing(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("version='1'", encoding="utf-8")
    facts = facts_at(tmp_path)
    fingerprint = fingerprint_facts(facts)

    assert classify_projects([facts], WorkspaceState({})) == {"demo": "new"}
    assert classify_projects(
        [facts], WorkspaceState({"demo": ProjectState(".", fingerprint, fingerprint)})
    ) == {"demo": "current"}
    assert classify_projects(
        [facts], WorkspaceState({"demo": ProjectState(".", "old", "old")})
    ) == {"demo": "stale"}
    assert classify_projects([], WorkspaceState({"gone": ProjectState("gone", "x", "x")})) == {
        "gone": "missing"
    }



def test_rejects_invalid_git_provenance_in_state(tmp_path: Path) -> None:
    write_state(tmp_path, WorkspaceState({"demo": ProjectState(".", "abc", "abc")}))
    path = tmp_path / ".ai/state.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["projects"]["demo"]["git_commit"] = 123
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(StateError, match="Git fields"):
        load_state(tmp_path, strict=True)
