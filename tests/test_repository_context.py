import json
from pathlib import Path
import subprocess

from ai_context_kit.cli import main
from ai_context_kit.harness_export import build_harness_bundle
from ai_context_kit.repository_context import evaluate_freshness, inspect_repository


def git(path: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def init(path: Path) -> None:
    path.mkdir()
    git(path, "init", "-b", "main")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "Test")


def commit(path: Path, contents: str) -> str:
    (path / "file.txt").write_text(contents, encoding="utf-8")
    git(path, "add", "file.txt")
    git(path, "commit", "-m", contents)
    return git(path, "rev-parse", "HEAD")


def test_non_git_and_unborn_repository(tmp_path: Path) -> None:
    outside = tmp_path / "not-a-repo"
    outside.mkdir()
    (outside / ".git").write_text("gitdir: nonexistent", encoding="utf-8")
    assert inspect_repository(outside).error == "not_git_repository"
    repo = tmp_path / "repo"
    init(repo)
    state = inspect_repository(repo)
    assert state.branch == "main"
    assert state.head_commit is None
    assert state.upstream is None
    assert evaluate_freshness(None, state).local == "unknown"


def test_clean_dirty_untracked_detached_and_commit_freshness(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init(repo)
    first = commit(repo, "one")
    state = inspect_repository(repo)
    assert state.dirty is False
    assert evaluate_freshness(first, state).local == "fresh"
    (repo / "file.txt").write_text("modified", encoding="utf-8")
    (repo / "new.txt").write_text("untracked", encoding="utf-8")
    state = inspect_repository(repo)
    assert state.dirty is True
    assert state.modified == 1
    assert state.untracked == 1
    assert evaluate_freshness(first, state).local == "potentially_stale"
    git(repo, "add", "file.txt")
    assert inspect_repository(repo).staged == 1
    git(repo, "commit", "-m", "two")
    (repo / "new.txt").unlink()
    state = inspect_repository(repo)
    assert evaluate_freshness(first, state).local == "potentially_stale"
    git(repo, "checkout", "--detach")
    assert inspect_repository(repo).branch is None


def test_cached_upstream_ahead_behind_and_diverged(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    remote.mkdir()
    git(remote, "init", "--bare")
    local = tmp_path / "local"
    init(local)
    commit(local, "one")
    git(local, "remote", "add", "origin", str(remote))
    git(local, "push", "-u", "origin", "main")
    assert (inspect_repository(local).ahead, inspect_repository(local).behind) == (0, 0)
    commit(local, "two")
    assert (inspect_repository(local).ahead, inspect_repository(local).behind) == (1, 0)
    peer = tmp_path / "peer"
    git(tmp_path, "clone", str(remote), str(peer))
    git(peer, "config", "user.email", "test@example.com")
    git(peer, "config", "user.name", "Test")
    git(peer, "checkout", "main")
    commit(peer, "peer")
    git(peer, "push", "origin", "main")
    git(local, "fetch", "origin")
    state = inspect_repository(local)
    assert (state.ahead, state.behind) == (1, 1)
    assert evaluate_freshness(state.head_commit, state).remote == "potentially_stale"
    git(local, "reset", "--hard", "HEAD~1")
    assert (inspect_repository(local).ahead, inspect_repository(local).behind) == (0, 1)
    git(local, "reset", "--hard", "origin/main")
    assert (inspect_repository(local).ahead, inspect_repository(local).behind) == (0, 0)


def test_cli_json_reports_context_commit(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    init(repo)
    head = commit(repo, "one")
    assert main(["repo", "inspect", str(repo), "--context-commit", head, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["repository"]["head_commit"] == head
    assert payload["context_freshness"]["local"] == "fresh"


def test_bundle_preserves_context_source_commit_after_head_moves(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repo = workspace / "demo"
    init(repo)
    (repo / "pyproject.toml").write_text('[project]\nname="demo"\n', encoding="utf-8")
    git(repo, "add", "pyproject.toml")
    git(repo, "commit", "-m", "initial")
    baseline = git(repo, "rev-parse", "HEAD")
    assert main(["init", "--workspace", str(workspace)]) == 0
    assert baseline in (workspace / ".ai/projects/demo.md").read_text(encoding="utf-8")
    record = build_harness_bundle(workspace, "demo")["repositories"][0]
    assert record["source"]["commit"] == baseline
    assert record["context_freshness"]["local"] == "fresh"
    commit(repo, "next")
    record = build_harness_bundle(workspace, "demo")["repositories"][0]
    assert record["source"]["commit"] == baseline
    assert record["head_commit"] != baseline
    assert record["context_freshness"]["local"] == "potentially_stale"
