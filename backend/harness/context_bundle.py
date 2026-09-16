from __future__ import annotations

from datetime import datetime
import json
from pathlib import PureWindowsPath
import re
from typing import Any

from audit.redaction import redact_value

from .models import FRESHNESS_VALUES, SCHEMA_VERSION

MAX_BUNDLE_BYTES = 512 * 1024
REQUIRED_FIELDS = {"schema_version", "project", "generated_at", "freshness", "observed_scope", "repositories", "context"}
ABSOLUTE_PATH_TOKEN = re.compile(r"(?<![:A-Za-z0-9+.-])(?:[A-Za-z]:[\\/]|\\\\[^\s]+|/(?!/))[^\s]*")


def _is_absolute(value: str) -> bool:
    return value.startswith("/") or PureWindowsPath(value).is_absolute()


def _contains_absolute_path(value: object) -> bool:
    if isinstance(value, dict):
        return any(_contains_absolute_path(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_absolute_path(item) for item in value)
    return isinstance(value, str) and (_is_absolute(value) or ABSOLUTE_PATH_TOKEN.search(value) is not None)


def validate_context_bundle(payload: dict[str, object]) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ValueError("context bundle must be an object")
    if len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) > MAX_BUNDLE_BYTES:
        raise ValueError("context bundle exceeds 512 KiB")
    missing = REQUIRED_FIELDS - payload.keys()
    if missing:
        raise ValueError(f"missing context bundle fields: {', '.join(sorted(missing))}")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
    if not isinstance(payload["project"], str) or not payload["project"].strip():
        raise ValueError("project is required")
    try:
        generated_at = datetime.fromisoformat(str(payload["generated_at"]).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("generated_at must be ISO 8601") from exc
    if generated_at.tzinfo is None:
        raise ValueError("generated_at must include a timezone")
    if payload["freshness"] not in FRESHNESS_VALUES:
        raise ValueError("invalid freshness")
    scope = payload["observed_scope"]
    if not isinstance(scope, list) or not all(isinstance(item, str) and item.strip() for item in scope):
        raise ValueError("observed_scope must be a list of non-empty strings")
    repositories = payload["repositories"]
    if not isinstance(repositories, list) or not repositories:
        raise ValueError("repositories must be a non-empty list")
    for repository in repositories:
        if not isinstance(repository, dict):
            raise ValueError("repository must be an object")
        path = repository.get("relative_path")
        if not isinstance(path, str) or not path.strip() or _is_absolute(path):
            raise ValueError("repository relative_path must not be absolute")
    if not isinstance(payload["context"], dict):
        raise ValueError("context must be an object")
    if _contains_absolute_path(payload["observed_scope"]) or _contains_absolute_path(payload["context"]):
        raise ValueError("context bundle must not contain absolute paths")
    return redact_value(payload)
