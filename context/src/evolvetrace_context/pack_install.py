"""Managed, reversible Personal AI Pack installation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .entrypoints import render_pack_files
from .personal_pack import PersonalAIPack
from .state import _atomic_text


def _digest(contents: str | bytes) -> str:
    encoded = contents.encode("utf-8") if isinstance(contents, str) else contents
    return hashlib.sha256(encoded).hexdigest()


class ManagedPackFileError(ValueError):
    """A managed Pack asset changed outside the installer."""

    def __init__(self, paths: tuple[str, ...]):
        self.paths = paths
        super().__init__("modified managed pack files: " + ", ".join(paths))


class PackInstaller:
    def __init__(self, target: Path):
        self.target = target.resolve()
        self.root = self.target / ".aictx-pack"
        self.state_path = self.root / "state.json"

    def install(self, pack: PersonalAIPack, manifest_path: Path) -> dict[str, Any]:
        del manifest_path  # source location is intentionally never persisted
        rendered = render_pack_files(pack)
        if self.state_path.exists():
            modified = self._modified(self._state())
            if modified:
                raise ManagedPackFileError(modified)
        for relative, contents in rendered.items():
            _atomic_text(self.root / relative, contents)
        state = {
            "schema": "personal-ai-pack-installation/v1",
            "pack": pack.to_public_summary(),
            "managed_files": {
                relative: _digest(contents) for relative, contents in sorted(rendered.items())
            },
        }
        _atomic_text(self.state_path, json.dumps(state, indent=2, sort_keys=True) + "\n")
        return state

    def _state(self) -> dict[str, Any]:
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        if payload.get("schema") != "personal-ai-pack-installation/v1":
            raise ValueError("unsupported installation state")
        return payload

    def status(self) -> dict[str, Any]:
        return self._state()

    def _modified(self, state: dict[str, Any]) -> tuple[str, ...]:
        modified: list[str] = []
        for relative, expected in state["managed_files"].items():
            path = self.root / relative
            if path.exists() and _digest(path.read_bytes()) != expected:
                modified.append(relative)
        return tuple(sorted(modified))

    def doctor(self) -> list[str]:
        try:
            state = self._state()
        except (OSError, ValueError, json.JSONDecodeError):
            return ["installation state is missing or invalid"]
        findings: list[str] = []
        for relative, expected in state["managed_files"].items():
            path = self.root / relative
            if not path.exists():
                findings.append(f"missing managed file: {relative}")
            elif _digest(path.read_bytes()) != expected:
                findings.append(f"digest mismatch: {relative}")
        return findings

    def uninstall(self) -> None:
        if not self.root.exists():
            return
        state = self._state()
        modified = self._modified(state)
        if modified:
            raise ManagedPackFileError(modified)
        for relative in state["managed_files"]:
            path = self.root / relative
            if path.exists():
                path.unlink()
        self.state_path.unlink(missing_ok=True)
        for directory in sorted(
            (path for path in self.root.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            try:
                directory.rmdir()
            except OSError:
                pass
        try:
            self.root.rmdir()
        except OSError:
            pass
