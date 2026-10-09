from pathlib import Path

import pytest

from ai_context_kit.config import ConfigError, find_workspace, load_config


def test_find_workspace_walks_upward(tmp_path: Path) -> None:
    (tmp_path / ".aictx.toml").write_text("version = 1\n", encoding="utf-8")
    nested = tmp_path / "projects" / "demo"
    nested.mkdir(parents=True)

    assert find_workspace(nested) == tmp_path.resolve()


def test_load_config_applies_defaults(tmp_path: Path) -> None:
    (tmp_path / ".aictx.toml").write_text("version = 1\n", encoding="utf-8")

    config = load_config(tmp_path)

    assert config.max_file_bytes == 1_048_576
    assert config.include == (".",)
    assert "node_modules" in config.exclude
    assert config.project_names == {}


def test_load_config_reads_overrides(tmp_path: Path) -> None:
    (tmp_path / ".aictx.toml").write_text(
        """version = 1
max_file_bytes = 99
[discovery]
include = ["projects"]
exclude = ["vendor"]
[projects]
"projects/demo" = "Demo App"
""",
        encoding="utf-8",
    )

    config = load_config(tmp_path)

    assert config.max_file_bytes == 99
    assert config.include == ("projects",)
    assert config.exclude == ("vendor",)
    assert config.project_names == {"projects/demo": "Demo App"}


@pytest.mark.parametrize(
    "contents",
    ["version = 2\n", 'version = 1\nmax_file_bytes = "large"\n'],
)
def test_load_config_rejects_unsupported_or_invalid_values(
    tmp_path: Path, contents: str
) -> None:
    (tmp_path / ".aictx.toml").write_text(contents, encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config(tmp_path)
