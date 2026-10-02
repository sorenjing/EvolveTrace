from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "self-check.ps1"
USAGE_GUIDE = ROOT / "docs" / "zh-CN" / "usage.md"
SELF_CHECK_GUIDE = ROOT / "docs" / "zh-CN" / "self-check.md"


def test_self_check_script_is_read_only_and_workspace_agnostic() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "[string]$Workspace" in text
    assert "aictx" in text
    for command in ("--version", "scan", "status", "check"):
        assert command in text
    for mutation in ("aictx update", "aictx init", "aictx install", "aictx uninstall"):
        assert mutation not in text
    assert "D:\\" not in text


def test_chinese_guides_cover_daily_use_and_health_checks() -> None:
    usage = USAGE_GUIDE.read_text(encoding="utf-8")
    self_check = SELF_CHECK_GUIDE.read_text(encoding="utf-8")

    for phrase in ("new", "stale", "current", "missing", "--dry-run", "manual"):
        assert phrase in usage
    for phrase in ("scripts/self-check.ps1", "aictx check", "aictx doctor", "只读"):
        assert phrase in self_check


def test_readme_links_to_chinese_guides() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "docs/zh-CN/usage.md" in readme
    assert "docs/zh-CN/self-check.md" in readme
