from pathlib import Path
import subprocess

import pytest

from ai_context_kit.personal_pack import PersonalAIPack
from ai_context_kit.workspace_discovery import resolve_workspace
from test_personal_pack import valid_pack_v2, write_pack


def pack(tmp_path: Path) -> PersonalAIPack:
    return PersonalAIPack.load(write_pack(tmp_path / "pack.json", valid_pack_v2()))


def portfolio(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "personal-ai-pack.yaml").write_text("schema: fixture\n", encoding="utf-8")
    (path / "registry.yaml").write_text("projects: {}\n", encoding="utf-8")
    return path


def test_discovers_sibling_portfolio_from_nested_project(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / ".aictx.toml").write_text("version = 1\n", encoding="utf-8")
    target = workspace / "projects" / "demo" / "src"
    target.mkdir(parents=True)
    expected = portfolio(workspace / "example" / "private-portfolio")

    result = resolve_workspace(start=target, pack=pack(tmp_path), environ={})

    assert result.status == "resolved"
    assert result.source == "discovery"
    assert result.workspace_root == workspace
    assert result.portfolio_root == expected


def test_explicit_paths_win_over_environment_and_discovery(tmp_path: Path) -> None:
    explicit_workspace = tmp_path / "explicit-workspace"
    explicit_workspace.mkdir()
    explicit_portfolio = portfolio(tmp_path / "explicit-portfolio")
    env_portfolio = portfolio(tmp_path / "env-portfolio")

    result = resolve_workspace(
        start=tmp_path,
        pack=pack(tmp_path),
        workspace=explicit_workspace,
        portfolio=explicit_portfolio,
        environ={"AICTX_PORTFOLIO_ROOT": str(env_portfolio)},
    )

    assert result.status == "resolved"
    assert result.source == "explicit"
    assert result.workspace_root == explicit_workspace
    assert result.portfolio_root == explicit_portfolio


def test_environment_resolves_separated_workspace_and_portfolio(tmp_path: Path) -> None:
    workspace = tmp_path / "code"
    workspace.mkdir()
    expected = portfolio(tmp_path / "private" / "private-portfolio")

    result = resolve_workspace(
        start=tmp_path,
        pack=pack(tmp_path),
        environ={
            "AICTX_WORKSPACE_ROOT": str(workspace),
            "AICTX_PORTFOLIO_ROOT": str(expected),
        },
    )

    assert result.status == "resolved"
    assert result.source == "environment"
    assert result.workspace_root == workspace
    assert result.portfolio_root == expected


def test_explicit_workspace_still_discovers_portfolio_inside_it(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    expected = portfolio(workspace / "private-portfolio")

    result = resolve_workspace(
        start=tmp_path,
        pack=pack(tmp_path),
        workspace=workspace,
        environ={},
    )

    assert result.status == "resolved"
    assert result.source == "explicit"
    assert result.workspace_root == workspace
    assert result.portfolio_root == expected


def test_environment_workspace_still_discovers_portfolio_inside_it(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    expected = portfolio(workspace / "private-portfolio")

    result = resolve_workspace(
        start=tmp_path,
        pack=pack(tmp_path),
        environ={"AICTX_WORKSPACE_ROOT": str(workspace)},
    )

    assert result.status == "resolved"
    assert result.source == "environment"
    assert result.portfolio_root == expected


def test_missing_environment_path_is_invalid_not_fallback(tmp_path: Path) -> None:
    portfolio(tmp_path / "example" / "private-portfolio")
    result = resolve_workspace(
        start=tmp_path,
        pack=pack(tmp_path),
        environ={"AICTX_PORTFOLIO_ROOT": str(tmp_path / "missing")},
    )
    assert result.status == "invalid"
    assert result.source == "environment"


def test_equal_portfolio_candidates_are_ambiguous_and_stable(tmp_path: Path) -> None:
    first = portfolio(tmp_path / "a" / "private-portfolio")
    second = portfolio(tmp_path / "b" / "private-portfolio")
    result = resolve_workspace(start=tmp_path, pack=pack(tmp_path), environ={})
    assert result.status == "ambiguous"
    assert result.candidates == (first, second)


def test_external_symlink_is_not_followed(tmp_path: Path) -> None:
    start = tmp_path / "workspace"
    start.mkdir()
    (start / ".aictx.toml").write_text("version = 1\n", encoding="utf-8")
    external = portfolio(tmp_path / "external" / "private-portfolio")
    try:
        (start / "private-portfolio").symlink_to(external, target_is_directory=True)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314:
            pytest.skip("Creating directory symlinks requires Windows privilege")
        raise

    result = resolve_workspace(start=start, pack=pack(tmp_path), environ={})

    assert result.status == "unresolved"
    assert external not in result.candidates


def test_excluded_directories_are_not_visited(tmp_path: Path) -> None:
    (tmp_path / ".aictx.toml").write_text("version = 1\n", encoding="utf-8")
    portfolio(tmp_path / "node_modules" / "private-portfolio")
    result = resolve_workspace(start=tmp_path, pack=pack(tmp_path), environ={})
    assert result.status == "unresolved"


def test_untracked_local_override_has_lower_precedence_than_environment(tmp_path: Path) -> None:
    override_portfolio = portfolio(tmp_path / "override-portfolio")
    env_portfolio = portfolio(tmp_path / "env-portfolio")
    override = tmp_path / ".aictx.local.toml"
    override.write_text(
        f'version = 1\nportfolio_root = "{override_portfolio}"\n', encoding="utf-8"
    )

    result = resolve_workspace(
        start=tmp_path,
        pack=pack(tmp_path),
        local_override=override,
        environ={"AICTX_PORTFOLIO_ROOT": str(env_portfolio)},
    )
    assert result.source == "environment"
    assert result.portfolio_root == env_portfolio


def test_tracked_local_override_is_rejected(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    expected = portfolio(tmp_path / "private-portfolio")
    override = tmp_path / ".aictx.local.toml"
    override.write_text(f'version = 1\nportfolio_root = "{expected}"\n', encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", ".aictx.local.toml"], check=True)

    result = resolve_workspace(
        start=tmp_path,
        pack=pack(tmp_path),
        local_override=override,
        environ={},
    )

    assert result.status == "invalid"
    assert result.source == "override"
    assert "tracked" in result.findings[0]


def test_discovery_never_persists_private_paths(tmp_path: Path) -> None:
    expected = portfolio(tmp_path / "private-portfolio")
    loaded_pack = pack(tmp_path)
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    result = resolve_workspace(start=tmp_path, pack=loaded_pack, environ={})
    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert result.portfolio_root == expected
    assert after == before
