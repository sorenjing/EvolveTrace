"""Build the unified plugin from an explicit, runtime-data-free payload."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import stat
import tempfile
import zipfile


PAYLOAD_FILES = (
    ".codex-plugin/plugin.json",
    "hooks/hooks.json",
    "plugin/hooks/capture_event.py",
    "plugin/hooks/safety_policy.py",
    "context/hooks/session_start.py",
    "context/skills/manage-ai-context/SKILL.md",
    "context/skills/manage-ai-context/agents/openai.yaml",
    "LICENSE",
    "context/LICENSE",
    "NOTICE",
    "README.md",
    "docs/consolidation.md",
)


def _reject_link(path: Path) -> None:
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    if path.is_symlink() or attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        raise ValueError("Plugin payload cannot contain a link or reparse point")


def build_archive(root: Path, output: Path) -> Path:
    _reject_link(root)
    root = root.resolve()
    output = output.resolve()
    if output.is_relative_to(root / "context/skills"):
        raise ValueError("Archive output must stay outside the canonical Skill")
    if output.suffix.lower() != ".zip":
        raise ValueError("Archive output must use the .zip suffix")
    sources = []
    for relative in PAYLOAD_FILES:
        current = root
        for part in Path(relative).parts:
            current = current / part
            _reject_link(current)
        if not current.is_file():
            raise ValueError(f"Missing plugin file: {relative}")
        sources.append((current, relative))
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".zip.tmp", delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with zipfile.ZipFile(temporary_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for source, relative in sources:
                archive.write(source, relative)
        os.replace(temporary_path, output)
    finally:
        temporary_path.unlink(missing_ok=True)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("dist/evolvetrace-plugin.zip"))
    args = parser.parse_args()
    print(build_archive(Path(__file__).resolve().parents[1], args.output))


if __name__ == "__main__":
    main()
