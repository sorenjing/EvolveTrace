"""Bounded, non-persistent discovery for Personal AI Pack workspaces."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import tomllib
from typing import Literal, Mapping

from .personal_pack import PersonalAIPack


_EXCLUDED = {
    ".git", ".ai", ".aictx-pack", "node_modules", ".venv", "venv",
    "dist", "build", "target", "coverage",
}


@dataclass(frozen=True)
class DiscoveryResult:
    status: Literal["resolved", "ambiguous", "unresolved", "invalid"]
    source: Literal["explicit", "environment", "override", "discovery", "none"]
    workspace_root: Path | None = None
    portfolio_root: Path | None = None
    candidates: tuple[Path, ...] = ()
    findings: tuple[str, ...] = ()


def _valid_directory(path: Path, label: str) -> tuple[Path | None, str | None]:
    resolved = path.expanduser().resolve()
    if not resolved.is_dir():
        return None, f"{label} is not an existing directory: {path}"
    return resolved, None


def _tracked(path: Path) -> bool:
    root = subprocess.run(
        ["git", "-C", str(path.parent), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if root.returncode != 0:
        return False
    repository = Path(root.stdout.strip()).resolve()
    try:
        relative = path.resolve().relative_to(repository)
    except ValueError:
        return False
    result = subprocess.run(
        ["git", "-C", str(repository), "ls-files", "--error-unmatch", "--", relative.as_posix()],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _load_override(path: Path) -> tuple[Path | None, Path | None]:
    if _tracked(path):
        raise ValueError("machine-local override is tracked by Git")
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"invalid machine-local override: {exc}") from exc
    allowed = {"version", "workspace_root", "portfolio_root"}
    if set(payload) - allowed or payload.get("version") != 1:
        raise ValueError("machine-local override fields are invalid")
    for key in ("workspace_root", "portfolio_root"):
        if key in payload and not isinstance(payload[key], str):
            raise ValueError(f"{key} must be a string")
    return (
        Path(payload["workspace_root"]) if payload.get("workspace_root") else None,
        Path(payload["portfolio_root"]) if payload.get("portfolio_root") else None,
    )


def _portfolio_name(pack: PersonalAIPack) -> str:
    portfolio = pack.sources.get("portfolio")
    if not isinstance(portfolio, dict) or not isinstance(portfolio.get("repository"), str):
        raise ValueError("pack portfolio repository is required for discovery")
    return portfolio["repository"].rstrip("/").rsplit("/", 1)[-1]


def _candidates(root: Path, *, name: str, max_depth: int) -> tuple[Path, ...]:
    found: list[Path] = []
    queue = deque([(root, 0)])
    while queue:
        current, depth = queue.popleft()
        if current.name == name and (
            (current / "personal-ai-pack.yaml").is_file() or (current / "registry.yaml").is_file()
        ):
            found.append(current.resolve())
            continue
        if depth >= max_depth:
            continue
        try:
            entries = sorted(current.iterdir(), key=lambda item: item.name.casefold())
        except OSError:
            continue
        for entry in entries:
            if entry.name in _EXCLUDED or entry.is_symlink():
                continue
            try:
                is_directory = entry.is_dir()
            except OSError:
                continue
            if is_directory:
                queue.append((entry, depth + 1))
    return tuple(sorted(set(found), key=lambda item: item.as_posix().casefold()))


def _configured_result(
    *, source: Literal["explicit", "environment", "override"],
    workspace: Path | None, portfolio: Path | None, portfolio_name: str, max_depth: int,
) -> DiscoveryResult:
    resolved_workspace = None
    resolved_portfolio = None
    findings: list[str] = []
    if workspace is not None:
        resolved_workspace, issue = _valid_directory(workspace, "workspace root")
        if issue:
            findings.append(issue)
    if portfolio is not None:
        resolved_portfolio, issue = _valid_directory(portfolio, "portfolio root")
        if issue:
            findings.append(issue)
    if findings:
        return DiscoveryResult("invalid", source, findings=tuple(findings))
    if resolved_workspace is None and resolved_portfolio is not None:
        resolved_workspace = resolved_portfolio.parent
    if resolved_portfolio is None:
        if resolved_workspace is None:
            return DiscoveryResult("unresolved", source)
        found = _candidates(resolved_workspace, name=portfolio_name, max_depth=max_depth)
        if len(found) == 1:
            return DiscoveryResult("resolved", source, resolved_workspace, found[0], found)
        if len(found) > 1:
            return DiscoveryResult("ambiguous", source, resolved_workspace, candidates=found)
        return DiscoveryResult("unresolved", source, workspace_root=resolved_workspace)
    return DiscoveryResult("resolved", source, resolved_workspace, resolved_portfolio)


def resolve_workspace(
    *,
    start: Path,
    pack: PersonalAIPack,
    workspace: Path | None = None,
    portfolio: Path | None = None,
    local_override: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> DiscoveryResult:
    """Resolve workspace and Portfolio without persisting local paths."""
    config = pack.entrypoints.local if pack.entrypoints is not None else None
    max_depth = config.max_depth if config is not None else 3
    workspace_env = config.workspace_env if config is not None else "AICTX_WORKSPACE_ROOT"
    portfolio_env = config.portfolio_env if config is not None else "AICTX_PORTFOLIO_ROOT"
    portfolio_name = _portfolio_name(pack)
    values = os.environ if environ is None else environ

    if workspace is not None or portfolio is not None:
        return _configured_result(
            source="explicit", workspace=workspace, portfolio=portfolio,
            portfolio_name=portfolio_name, max_depth=max_depth,
        )

    environment_workspace = Path(values[workspace_env]) if values.get(workspace_env) else None
    environment_portfolio = Path(values[portfolio_env]) if values.get(portfolio_env) else None
    if environment_workspace is not None or environment_portfolio is not None:
        return _configured_result(
            source="environment", workspace=environment_workspace, portfolio=environment_portfolio,
            portfolio_name=portfolio_name, max_depth=max_depth,
        )

    if local_override is not None:
        try:
            override_workspace, override_portfolio = _load_override(local_override.resolve())
        except ValueError as exc:
            return DiscoveryResult("invalid", "override", findings=(str(exc),))
        if override_workspace is not None or override_portfolio is not None:
            return _configured_result(
                source="override", workspace=override_workspace, portfolio=override_portfolio,
                portfolio_name=portfolio_name, max_depth=max_depth,
            )

    origin = start.resolve()
    if not origin.is_dir():
        return DiscoveryResult("invalid", "discovery", findings=(f"start is not a directory: {start}",))
    root = origin
    for _ in range(max_depth + 1):
        found = _candidates(root, name=portfolio_name, max_depth=max_depth)
        if len(found) == 1:
            return DiscoveryResult("resolved", "discovery", root, found[0], found)
        if len(found) > 1:
            return DiscoveryResult("ambiguous", "discovery", root, candidates=found)
        if (root / ".aictx.toml").is_file() or (root / ".git").exists():
            break
        if root.parent == root:
            break
        root = root.parent
    return DiscoveryResult("unresolved", "none")
