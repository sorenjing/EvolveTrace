from pathlib import Path
import subprocess

from ai_context_kit.config import Config
from ai_context_kit.facts import extract_facts
from ai_context_kit.models import Project


def project_at(root: Path) -> Project:
    return Project(name=root.name, path=root.resolve(), relative_path=".", markers=("pyproject.toml",))


def test_extracts_python_node_readme_and_directories(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="demo"\ndependencies=["requests>=2"]\n'
        '[project.scripts]\ndemo="demo:main"\n',
        encoding="utf-8",
    )
    (tmp_path / "package.json").write_text(
        '{"name":"web","scripts":{"test":"vitest","dev":"vite"},"dependencies":{"react":"latest"}}',
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        "# Demo\n\nAn offline context example.\n\nMore details.", encoding="utf-8"
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()

    facts = extract_facts(project_at(tmp_path), Config(root=tmp_path.resolve()))

    assert facts.description == "An offline context example."
    assert "Python" in facts.technologies
    assert "Node.js" in facts.technologies
    assert ("demo", "demo:main") in facts.commands
    assert ("npm run test", "vitest") in facts.commands
    assert facts.directories == ("src", "tests")
    assert {path.name for path in facts.scanned_files} >= {"pyproject.toml", "package.json", "README.md"}


def test_reports_git_metadata_without_failing_outside_git(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "pyproject.toml"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True)

    facts = extract_facts(project_at(tmp_path), Config(root=tmp_path.resolve()))

    assert facts.git_branch == "main"
    assert facts.git_head is not None and len(facts.git_head) == 40
    assert facts.git_dirty is False


def test_ignores_oversized_readme(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Large\n\nsecret", encoding="utf-8")

    facts = extract_facts(project_at(tmp_path), Config(root=tmp_path.resolve(), max_file_bytes=3))

    assert facts.description is None
    assert Path("README.md") not in facts.scanned_files
