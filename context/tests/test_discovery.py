from pathlib import Path

from ai_context_kit.config import Config
from ai_context_kit.discovery import discover_projects


def config_for(root: Path) -> Config:
    return Config(root=root.resolve())


def test_discovers_projects_and_skips_nested_packages(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='root'\n", encoding="utf-8")
    nested = tmp_path / "packages" / "child"
    nested.mkdir(parents=True)
    (nested / "package.json").write_text('{"name":"child"}', encoding="utf-8")

    projects = discover_projects(config_for(tmp_path))

    assert [project.relative_path for project in projects] == ["."]


def test_nested_git_repository_is_a_separate_project(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='root'\n", encoding="utf-8")
    nested = tmp_path / "projects" / "child"
    (nested / ".git").mkdir(parents=True)
    (nested / "package.json").write_text('{"name":"child"}', encoding="utf-8")

    projects = discover_projects(config_for(tmp_path))

    assert [project.relative_path for project in projects] == [".", "projects/child"]


def test_excludes_dependency_directories(tmp_path: Path) -> None:
    hidden = tmp_path / "node_modules" / "dependency"
    hidden.mkdir(parents=True)
    (hidden / ".git").mkdir()

    assert discover_projects(config_for(tmp_path)) == []


def test_does_not_follow_directory_symlinks(tmp_path: Path) -> None:
    external = tmp_path / "external"
    external.mkdir()
    (external / "go.mod").write_text("module example.com/external\n", encoding="utf-8")
    link = tmp_path / "linked"
    try:
        link.symlink_to(external, target_is_directory=True)
    except OSError:
        return

    projects = discover_projects(
        Config(root=tmp_path.resolve(), include=("linked",), exclude=())
    )
    assert projects == []

