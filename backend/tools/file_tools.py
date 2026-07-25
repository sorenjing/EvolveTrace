"""
文件操作工具：读取、写入、修改文件。
所有操作受 PROJECT_ROOT 沙箱限制。
"""
import os
import shutil
from pathlib import Path
from typing import Any

from config import PROJECT_ROOT
from auth.permissions import get_permission_cache

_perm = get_permission_cache()

# 自定义工具目录：禁止 write_file/edit_file 直接写入，须走 create_tool（含 AST 审查）
_CUSTOM_TOOLS_DIR = (PROJECT_ROOT / "backend" / "tools" / "custom").resolve()


def _reject_custom_tools_path(target: Path) -> str | None:
    """若目标落在 custom/ 工具目录内，返回错误信息。"""
    try:
        if target == _CUSTOM_TOOLS_DIR or target.is_relative_to(_CUSTOM_TOOLS_DIR):
            return "[错误] 禁止直接写入自定义工具目录，请使用 create_tool 创建工具"
    except AttributeError:
        if target == _CUSTOM_TOOLS_DIR or _CUSTOM_TOOLS_DIR in target.parents:
            return "[错误] 禁止直接写入自定义工具目录，请使用 create_tool 创建工具"
    return None


def read_file(path: str) -> str:
    """读取文件内容，支持文本文件。"""
    try:
        target = _perm.resolve_within_root(path, PROJECT_ROOT)
        if not target.exists():
            return f"[错误] 文件不存在: {target}"
        if target.is_dir():
            return f"[错误] 路径是目录: {target}"
        # 限制大小 1MB
        if target.stat().st_size > 1 * 1024 * 1024:
            return f"[错误] 文件超过 1MB，拒绝读取"
        return target.read_text(encoding="utf-8", errors="replace")
    except PermissionError as e:
        return f"[错误] 权限拒绝: {e}"
    except Exception as e:
        return f"[错误] 读取失败: {e}"


def write_file(path: str, content: str) -> str:
    """写入/覆盖文件。若目录不存在则自动创建。"""
    role = _perm.get_role_config()
    if not role.get("allow_file_write", False):
        return "[错误] 当前角色禁止写入文件"

    try:
        target = _perm.resolve_within_root(path, PROJECT_ROOT)
        blocked = _reject_custom_tools_path(target)
        if blocked:
            return blocked
        # 备份（若文件已存在且大小 > 0）
        if target.exists() and target.stat().st_size > 0:
            backup = target.with_suffix(target.suffix + ".bak")
            shutil.copy2(target, backup)

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"[成功] 已写入 {target}"
    except PermissionError as e:
        return f"[错误] 权限拒绝: {e}"
    except Exception as e:
        return f"[错误] 写入失败: {e}"


def edit_file(path: str, search: str, replace: str) -> str:
    """基于 Search/Replace 修改文件内容。"""
    role = _perm.get_role_config()
    if not role.get("allow_file_write", False):
        return "[错误] 当前角色禁止修改文件"

    try:
        target = _perm.resolve_within_root(path, PROJECT_ROOT)
        blocked = _reject_custom_tools_path(target)
        if blocked:
            return blocked
        if not target.exists():
            return f"[错误] 文件不存在: {target}"

        content = target.read_text(encoding="utf-8", errors="replace")
        if search not in content:
            return f"[错误] 未找到匹配内容，请确认 search 文本准确。文件当前前500字符:\n{content[:500]}"

        new_content = content.replace(search, replace, 1)
        if new_content == content:
            return "[警告] 替换后内容无变化"

        # 备份
        backup = target.with_suffix(target.suffix + ".bak")
        shutil.copy2(target, backup)

        target.write_text(new_content, encoding="utf-8")
        return f"[成功] 已修改 {target}"
    except PermissionError as e:
        return f"[错误] 权限拒绝: {e}"
    except Exception as e:
        return f"[错误] 修改失败: {e}"


def delete_file(path: str) -> str:
    """删除文件（需角色具备 allow_file_delete）。"""
    role = _perm.get_role_config()
    if not role.get("allow_file_delete", False):
        return "[错误] 当前角色禁止删除文件"

    try:
        target = _perm.resolve_within_root(path, PROJECT_ROOT)
        if not target.exists():
            return f"[错误] 文件不存在: {target}"
        if target.is_dir():
            return "[错误] 不能直接删除目录"
        target.unlink()
        return f"[成功] 已删除 {target}"
    except PermissionError as e:
        return f"[错误] 权限拒绝: {e}"
    except Exception as e:
        return f"[错误] 删除失败: {e}"
