from pathlib import Path

from ai_context_kit.entrypoints import render_pack_files
from ai_context_kit.personal_pack import PersonalAIPack
from test_personal_pack import valid_pack_v2, write_pack


def load_v2(tmp_path: Path) -> PersonalAIPack:
    return PersonalAIPack.load(write_pack(tmp_path / "pack.json", valid_pack_v2()))


def test_render_pack_files_share_one_policy_and_thin_platform_adapters(tmp_path: Path) -> None:
    rendered = render_pack_files(load_v2(tmp_path))

    assert sorted(rendered) == [
        "generated/common/entry-policy.md",
        "generated/local/local-workspace.md",
        "generated/openai/entrypoints/chatgpt.md",
        "generated/openai/entrypoints/codex.md",
        "generated/openai/plugin.json",
        "generated/openai/skills/manage-ai-context/SKILL.md",
    ]
    for path, contents in rendered.items():
        if path.endswith("plugin.json"):
            continue
        assert "generated/common/entry-policy.md" in contents
        assert "minimum" in contents.lower()
        assert "do not guess" in contents.lower()
        assert "sources" in contents.lower()


def test_rendered_entrypoints_match_platform_capabilities(tmp_path: Path) -> None:
    rendered = render_pack_files(load_v2(tmp_path))
    local = rendered["generated/local/local-workspace.md"]
    codex = rendered["generated/openai/entrypoints/codex.md"]
    chatgpt = rendered["generated/openai/entrypoints/chatgpt.md"]

    assert "bounded" in local.lower()
    assert "fixed absolute path" in local.lower()
    for phrase in ("AGENTS.md", ".ai/GLOBAL.md", ".ai/WORKSPACE.md", "aictx status", "branch", "worktree"):
        assert phrase in codex
    for phrase in ("MCP", "GitHub Connector", "reviewed handoff", "cannot inspect local directories"):
        assert phrase in chatgpt


def test_rendered_assets_never_embed_private_sources_or_machine_paths(tmp_path: Path) -> None:
    rendered = "\n".join(render_pack_files(load_v2(tmp_path)).values())
    for forbidden in ("sorenjing", "interview-notes", "MediaAI", "C:\\", "/home/", "example/private-portfolio"):
        assert forbidden not in rendered
