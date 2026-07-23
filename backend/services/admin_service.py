"""
管理服务：角色、命令白名单、LLM 能力探测、沙箱清理。
"""
from typing import Any

from auth.permissions import get_permission_cache
from auth.capability import get_llm_capability
from tools.cleanup import cleanup_all, cleanup_backups, cleanup_screenshots
from exceptions import AppError
from logger import get_logger

log = get_logger("admin_service")


# ---------- 角色管理 ----------

def set_role(role: str) -> dict[str, Any]:
    perm = get_permission_cache()
    try:
        perm.set_role(role)
    except ValueError as e:
        raise AppError(str(e), code="invalid_role")
    return {"role": role, "config": perm.get_role_config(role)}


def get_role() -> dict[str, Any]:
    perm = get_permission_cache()
    return {"role": perm.get_role(), "config": perm.get_role_config()}


# ---------- 命令白名单 ----------

def update_whitelist(command_prefix: str, action: str) -> dict[str, Any]:
    perm = get_permission_cache()
    if action == "add":
        perm.add_whitelist(command_prefix)
    elif action == "remove":
        perm.remove_whitelist(command_prefix)
    else:
        raise AppError("action 必须是 add 或 remove", code="invalid_action")
    return {"whitelist": perm.get_whitelist()}


# ---------- LLM 能力探测 ----------

def get_capability(model: str) -> dict[str, Any]:
    cap = get_llm_capability(model)
    return {"model": model, "supports_vision": cap.supports_vision}


def set_capability(model: str, vision: bool) -> dict[str, Any]:
    cap = get_llm_capability(model)
    cap.force_set(vision)
    return {"model": model, "supports_vision": cap.supports_vision}


# ---------- 沙箱清理 ----------

def run_cleanup() -> dict[str, Any]:
    return cleanup_all()


def cleanup_status() -> dict[str, Any]:
    backups = cleanup_backups(max_age_hours=0)
    screenshots = cleanup_screenshots(max_age_hours=0, max_count=999)
    return {
        "backups_count": len(backups.get("kept", [])),
        "screenshots_count": len(screenshots.get("removed", [])),
    }
