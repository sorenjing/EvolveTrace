"""Create a commit-ready, explicitly reviewed GitHub publication tree."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from .config import ConfigError
from .harness_export import SCHEMA_VERSION, build_harness_bundle
from .render import slugify
from .state import _atomic_text


INDEX_SCHEMA_VERSION = "context-bundle-index/v1"


def _load_index(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"schema_version": INDEX_SCHEMA_VERSION, "projects": []}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ConfigError(f"invalid publication index: {exc}") from exc
    if value.get("schema_version") != INDEX_SCHEMA_VERSION or not isinstance(
        value.get("projects"), list
    ):
        raise ConfigError("invalid publication index schema")
    return value


def publish_bundle(
    workspace: Path,
    project_name: str,
    destination: Path,
    *,
    generated_at: datetime | None = None,
) -> Path:
    """Write one bundle and update its deterministic publication index locally."""

    bundle = build_harness_bundle(workspace, project_name, generated_at=generated_at)
    root = destination.resolve()
    project_path = Path("projects") / f"{slugify(str(bundle['project']))}.json"
    output = root / project_path
    _atomic_text(output, json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    index_path = root / "index.json"
    index = _load_index(index_path)
    entries = [
        item
        for item in index["projects"]
        if isinstance(item, dict) and item.get("project") != bundle["project"]
    ]
    entries.append(
        {
            "project": bundle["project"],
            "path": project_path.as_posix(),
            "schema_version": SCHEMA_VERSION,
            "generated_at": bundle["generated_at"],
        }
    )
    index["projects"] = sorted(entries, key=lambda item: str(item["project"]).casefold())
    _atomic_text(index_path, json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return output

