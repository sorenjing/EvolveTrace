import json
from pathlib import Path

import pytest

from ai_context_kit.pack_install import ManagedPackFileError, PackInstaller
from ai_context_kit.personal_pack import PersonalAIPack
from test_personal_pack import valid_pack, write_pack


def test_install_status_doctor_update_and_uninstall_are_managed(tmp_path: Path) -> None:
    source = write_pack(tmp_path / "pack.json", valid_pack())
    target = tmp_path / "installation"
    installer = PackInstaller(target)
    pack = PersonalAIPack.load(source)

    state = installer.install(pack, source)
    assert state["schema"] == "personal-ai-pack-installation/v1"
    assert sorted(state["managed_files"]) == [
        "generated/common/entry-policy.md",
        "generated/local/local-workspace.md",
        "generated/openai/entrypoints/chatgpt.md",
        "generated/openai/entrypoints/codex.md",
        "generated/openai/plugin.json",
        "generated/openai/skills/manage-ai-context/SKILL.md",
    ]
    assert installer.status()["pack"]["id"] == "example-personal-ai"
    assert installer.doctor() == []

    plugin = target / ".aictx-pack/generated/openai/plugin.json"
    original_plugin = plugin.read_bytes()
    plugin.write_text("{}\n", encoding="utf-8")
    assert installer.doctor() == ["digest mismatch: generated/openai/plugin.json"]

    with pytest.raises(ManagedPackFileError):
        installer.install(pack, source)
    plugin.write_bytes(original_plugin)
    installer.install(pack, source)
    assert installer.doctor() == []
    unrelated = target / "keep.txt"
    unrelated.write_text("keep", encoding="utf-8")
    installer.uninstall()
    assert unrelated.read_text(encoding="utf-8") == "keep"
    assert not (target / ".aictx-pack").exists()


def test_status_never_exposes_manifest_path_or_sources(tmp_path: Path) -> None:
    source = write_pack(tmp_path / "private-pack.json", valid_pack())
    installer = PackInstaller(tmp_path / "installation")
    installer.install(PersonalAIPack.load(source), source)
    rendered = json.dumps(installer.status())
    assert str(tmp_path) not in rendered
    assert "private-portfolio" not in rendered


def test_reinstall_refuses_to_overwrite_modified_managed_file(tmp_path: Path) -> None:
    source = write_pack(tmp_path / "pack.json", valid_pack())
    installer = PackInstaller(tmp_path / "installation")
    pack = PersonalAIPack.load(source)
    installer.install(pack, source)
    codex = installer.root / "generated/openai/entrypoints/codex.md"
    common = installer.root / "generated/common/entry-policy.md"
    codex.write_text("user changes\n", encoding="utf-8")
    common_before = common.read_bytes()

    with pytest.raises(ManagedPackFileError, match="codex.md"):
        installer.install(pack, source)

    assert codex.read_text(encoding="utf-8") == "user changes\n"
    assert common.read_bytes() == common_before


def test_reinstall_restores_missing_managed_file(tmp_path: Path) -> None:
    source = write_pack(tmp_path / "pack.json", valid_pack())
    installer = PackInstaller(tmp_path / "installation")
    pack = PersonalAIPack.load(source)
    installer.install(pack, source)
    missing = installer.root / "generated/openai/entrypoints/codex.md"
    missing.unlink()

    installer.install(pack, source)

    assert missing.exists()
    assert installer.doctor() == []


def test_uninstall_refuses_modified_file_and_preserves_unrelated_file(tmp_path: Path) -> None:
    source = write_pack(tmp_path / "pack.json", valid_pack())
    target = tmp_path / "installation"
    installer = PackInstaller(target)
    installer.install(PersonalAIPack.load(source), source)
    modified = installer.root / "generated/local/local-workspace.md"
    modified.write_text("user changes\n", encoding="utf-8")
    unrelated = target / "keep.txt"
    unrelated.write_text("keep", encoding="utf-8")

    with pytest.raises(ManagedPackFileError, match="local-workspace.md"):
        installer.uninstall()

    assert modified.read_text(encoding="utf-8") == "user changes\n"
    assert unrelated.read_text(encoding="utf-8") == "keep"


def test_crlf_conversion_counts_as_modified_managed_bytes(tmp_path: Path) -> None:
    source = write_pack(tmp_path / "pack.json", valid_pack())
    installer = PackInstaller(tmp_path / "installation")
    installer.install(PersonalAIPack.load(source), source)
    managed = installer.root / "generated/openai/entrypoints/codex.md"
    managed.write_bytes(managed.read_bytes().replace(b"\n", b"\r\n"))

    with pytest.raises(ManagedPackFileError, match="codex.md"):
        installer.uninstall()
