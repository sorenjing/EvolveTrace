from pathlib import Path

import pytest

from ai_context_kit.adapters import ManagedFileError, render_adapters, write_managed_file


def test_renders_all_supported_ai_entry_files() -> None:
    adapters = render_adapters()

    assert set(path.as_posix() for path in adapters) == {
        "AGENTS.md",
        "CLAUDE.md",
        "GEMINI.md",
        ".cursor/rules/ai-context.mdc",
    }
    assert all(".ai/WORKSPACE.md" in contents for contents in adapters.values())
    assert all("nearest ancestor" in contents for contents in adapters.values())


def test_refuses_to_overwrite_unrecognized_entry_file(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text("my instructions", encoding="utf-8")

    with pytest.raises(ManagedFileError):
        write_managed_file(target, "generated", dry_run=False)


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"

    changed = write_managed_file(target, "generated", dry_run=True)

    assert changed is True
    assert not target.exists()
