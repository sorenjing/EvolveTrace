"""Read-only Git repository observations and context freshness decisions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import subprocess


@dataclass(frozen=True)
class RepositoryContext:
    path: Path
    repository_name: str
    branch: str | None
    head_commit: str | None
    upstream: str | None
    remote: str | None
    dirty: bool | None
    staged: int | None
    modified: int | None
    untracked: int | None
    ahead: int | None
    behind: int | None
    inspected_at: str
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {**asdict(self), "path": str(self.path)}


@dataclass(frozen=True)
class RepositoryFreshness:
    local: str
    remote: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {"local": self.local, "remote": self.remote, "reasons": list(self.reasons)}


def _git(path: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *args], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=3, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.rstrip("\r\n") if result.returncode == 0 else None


def inspect_repository(path: Path) -> RepositoryContext:
    """Inspect local refs only; never contact a remote or change the repository."""
    requested = path.resolve()
    stamp = datetime.now(timezone.utc).isoformat()
    root_text = _git(requested, "rev-parse", "--show-toplevel")
    if root_text is None:
        return RepositoryContext(requested, requested.name, None, None, None, None,
                                 None, None, None, None, None, None, stamp, "not_git_repository")
    root = Path(root_text).resolve()
    head = _git(root, "rev-parse", "--verify", "HEAD")
    branch = _git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    upstream = _git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}") if branch else None
    remote = upstream.split("/", 1)[0] if upstream and "/" in upstream else None
    status = _git(root, "status", "--porcelain=v1", "--untracked-files=normal")
    staged = modified = untracked = None
    if status is not None:
        staged = modified = untracked = 0
        for line in status.splitlines():
            if line.startswith("??"):
                untracked += 1
            elif len(line) >= 2:
                staged += line[0] != " "
                modified += line[1] != " "
    ahead = behind = None
    if upstream and head:
        counts = _git(root, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
        if counts:
            try:
                ahead, behind = (int(value) for value in counts.split())
            except ValueError:
                pass
    return RepositoryContext(root, root.name, branch, head, upstream, remote,
                             None if status is None else bool(status), staged, modified,
                             untracked, ahead, behind, stamp,
                             "status_unavailable" if status is None else None)


def evaluate_freshness(context_commit: str | None, repository: RepositoryContext) -> RepositoryFreshness:
    """Assess a saved context against local HEAD and cached upstream refs."""
    reasons: list[str] = []
    if repository.error or not context_commit or not repository.head_commit:
        local = "unknown"
        reasons.append("repository_or_context_commit_unavailable")
    elif context_commit != repository.head_commit:
        local = "potentially_stale"
        reasons.append("head_changed")
    elif repository.dirty is None:
        local = "unknown"
        reasons.append("working_tree_unavailable")
    elif repository.dirty:
        local = "potentially_stale"
        reasons.append("working_tree_dirty")
    else:
        local = "fresh"
    if repository.upstream is None or repository.behind is None:
        remote = "unknown"
        reasons.append("upstream_unavailable")
    elif repository.behind > 0:
        remote = "potentially_stale"
        reasons.append("behind_cached_upstream")
    else:
        remote = "fresh"
    return RepositoryFreshness(local, remote, tuple(reasons))
