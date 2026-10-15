"""Guard the component's canonical identity across executable surfaces."""

import json
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_distribution_and_import_use_evolvetrace_context():
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["project"]["name"] == "evolvetrace-context"
    assert metadata["project"]["scripts"] == {
        "aictx": "evolvetrace_context.cli:entrypoint",
        "aictx-mcp": "evolvetrace_context.mcp_server:entrypoint",
    }
    assert (ROOT / "src/evolvetrace_context/__main__.py").is_file()
    assert not (ROOT / "src/ai_context_kit").exists()
    assert metadata["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["src/evolvetrace_context"]


def test_plugin_and_mcp_examples_use_the_component_identity():
    for relative in ("plugin.json", ".codex-plugin/plugin.json"):
        manifest = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        assert manifest["name"] == "evolvetrace-context"
    example = json.loads((ROOT / "mcp.example.json").read_text(encoding="utf-8"))
    assert list(example["mcpServers"]) == ["evolvetrace-context"]


def test_active_source_has_no_predecessor_identity_and_license_is_retained():
    forbidden = ("ai_context_kit", "ai-context-kit", "AI Context Kit")
    sources = list((ROOT / "src/evolvetrace_context").rglob("*.py"))
    sources += [ROOT / "hooks/session_start.py", ROOT / "scripts/self-check.ps1", ROOT / "SECURITY.md"]
    for source in sources:
        text = source.read_text(encoding="utf-8")
        assert not any(name in text for name in forbidden), source
    assert "Copyright (c) 2026 AI Context Kit contributors" in (ROOT / "LICENSE").read_text(encoding="utf-8")
