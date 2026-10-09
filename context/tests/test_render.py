from pathlib import Path

import pytest

from ai_context_kit.models import Project, ProjectFacts
from ai_context_kit.render import MarkerError, render_project_memory, render_workspace


def sample_facts() -> ProjectFacts:
    return ProjectFacts(
        Project("Demo App", Path("/workspace/demo"), "projects/demo", ("package.json",)),
        "A useful demo.",
        ("Node.js",),
        (("npm run test", "vitest"),),
        ("src", "tests"),
        "main",
        "abc123",
        False,
        (Path("package.json"),),
    )


def test_render_project_memory_preserves_manual_block_exactly() -> None:
    existing = """# Old
<!-- aictx:auto:start -->
old facts
<!-- aictx:auto:end -->
<!-- aictx:manual:start -->
Keep  trailing spaces.  
中文记忆
<!-- aictx:manual:end -->
"""

    rendered = render_project_memory(sample_facts(), existing)

    assert "old facts" not in rendered
    assert "Keep  trailing spaces.  \n中文记忆" in rendered
    assert "npm run test: `vitest`" in rendered


def test_render_project_memory_discloses_bounded_observation_scope() -> None:
    rendered = render_project_memory(sample_facts())

    assert "## Observation scope" in rendered
    assert "Recognized metadata: `package.json`" in rendered
    assert "Git metadata: branch, HEAD, and working-tree state" in rendered
    assert "Directory metadata: immediate child directory names" in rendered
    assert "not a full source-code analysis" in rendered


@pytest.mark.parametrize(
    "existing",
    [
        "<!-- aictx:auto:start -->x<!-- aictx:auto:end -->",
        "<!-- aictx:auto:end --><!-- aictx:auto:start --><!-- aictx:manual:start --><!-- aictx:manual:end -->",
        "<!-- aictx:auto:start --><!-- aictx:auto:start --><!-- aictx:auto:end --><!-- aictx:manual:start --><!-- aictx:manual:end -->",
    ],
)
def test_render_rejects_malformed_markers(existing: str) -> None:
    with pytest.raises(MarkerError):
        render_project_memory(sample_facts(), existing)


def test_workspace_render_is_deterministic_and_uses_posix_paths() -> None:
    rendered = render_workspace([sample_facts()])

    assert "projects/demo" in rendered
    assert "Demo App" in rendered
    assert rendered == render_workspace([sample_facts()])
