import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "skills" / "manage-ai-context"


def test_skill_has_valid_trigger_and_cli_workflow() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

    assert text.startswith("---\nname: manage-ai-context\ndescription: Use when")
    for command in ("aictx init", "aictx status", "aictx update", "aictx check"):
        assert command in text
    assert "TODO" not in text
    assert "nearest ancestor" in text


def test_skill_routes_unknown_workspaces_through_bounded_locate() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

    assert "aictx locate" in text
    assert "ambiguous" in text.lower()
    assert "unbounded" in text.lower()
    assert "home directory" in text.lower()
    assert "private repository names" in text.lower()


def test_skill_has_codex_interface_metadata() -> None:
    metadata = (SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")

    assert 'display_name: "Manage AI Context"' in metadata
    assert "$manage-ai-context" in metadata


def test_plugin_manifest_exposes_the_standard_skill_directory() -> None:
    manifest = json.loads(
        (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )

    assert manifest["name"] == "ai-context-kit"
    assert manifest["version"] == "0.2.0"
    assert manifest["skills"] == "./skills/"
    assert manifest["repository"] == "https://github.com/sorenjing/ai-context-kit"
    assert manifest["interface"]["displayName"] == "AI Context Kit"
    assert "mcpServers" not in manifest
    assert "apps" not in manifest


def test_portable_plugin_manifest_is_canonical() -> None:
    manifest = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))

    assert manifest["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    assert manifest["name"] == "ai-context-kit"
    assert (ROOT / "skills/manage-ai-context/SKILL.md").exists()


def test_plugin_has_one_canonical_skill_location() -> None:
    assert SKILL.is_dir()
    assert not (ROOT / "skill").exists()


def test_python_package_includes_the_canonical_skill() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '"skills/manage-ai-context" = "share/ai-context-kit/skills/manage-ai-context"' in pyproject
