"""
权限缓存系统：管理 Agent 角色、命令白名单、文件操作边界。
"""
import re
from typing import Set, Dict, Any
from pathlib import Path
import threading


class PermissionCache:
    """线程安全的权限缓存，支持运行时动态调整。"""

    def __init__(self):
        self._lock = threading.RLock()
        # 命令白名单：只允许这些命令/子命令前缀
        self._cmd_whitelist: Set[str] = {
            "npm", "node", "npx", "python", "python3", "pip",
            "git status", "git diff", "git log", "git branch",
            "dir", "ls", "cat", "echo", "mkdir", "cd",
            "type", "findstr", "where",
        }
        # 角色权限映射
        self._roles: Dict[str, Dict[str, Any]] = {
            "standard": {
                "allow_file_write": True,
                "allow_file_delete": False,
                "allow_kernel_mutation": False,
                "allow_screenshot": True,
                "max_cmd_timeout": 60,
            },
            "admin": {
                "allow_file_write": True,
                "allow_file_delete": True,
                "allow_kernel_mutation": True,
                "allow_screenshot": True,
                "max_cmd_timeout": 300,
            },
            "readonly": {
                "allow_file_write": False,
                "allow_file_delete": False,
                "allow_kernel_mutation": False,
                "allow_screenshot": False,
                "max_cmd_timeout": 30,
            },
        }
        self._active_role: str = "standard"
        # 额外黑名单正则（优先级高于白名单）
        self._blacklist_patterns: list[re.Pattern] = [
            re.compile(r"rm\s+-rf\s+/"),
            re.compile(r"dd\s+if="),
            re.compile(r">\s*/dev/"),
            re.compile(r":\)\s*\{.*:\}.*\""),  # bash fork bomb 简单防护
        ]

    # ---------- 角色管理 ----------

    def set_role(self, role: str) -> None:
        with self._lock:
            if role not in self._roles:
                raise ValueError(f"未知角色: {role}，可用: {list(self._roles.keys())}")
            self._active_role = role

    def get_role(self) -> str:
        with self._lock:
            return self._active_role

    def get_role_config(self, role: str | None = None) -> Dict[str, Any]:
        with self._lock:
            r = role or self._active_role
            return self._roles.get(r, self._roles["standard"]).copy()

    def update_role_config(self, role: str, updates: Dict[str, Any]) -> None:
        with self._lock:
            if role not in self._roles:
                self._roles[role] = {}
            self._roles[role].update(updates)

    # ---------- 命令白名单 ----------

    def add_whitelist(self, cmd_prefix: str) -> None:
        with self._lock:
            self._cmd_whitelist.add(cmd_prefix.strip().lower())

    def remove_whitelist(self, cmd_prefix: str) -> None:
        with self._lock:
            self._cmd_whitelist.discard(cmd_prefix.strip().lower())

    def get_whitelist(self) -> list[str]:
        """返回当前命令白名单的排序副本。"""
        with self._lock:
            return sorted(self._cmd_whitelist)

    def check_command(self, command: str) -> tuple[bool, str]:
        """
        检查命令是否允许执行。
        返回 (is_allowed, reason)

        安全策略（三层防御）：
        1. 黑名单正则：拦截 rm -rf /、fork bomb 等危险模式
        2. 元字符禁用：禁止 ; & | ` $ > < 换行 等 shell 连接符，
           防止 `npm; rm -rf x` 这类通过白名单前缀绕过的注入
        3. 白名单精确匹配：用 shlex 解析命令名（及可选子命令），
           必须精确命中白名单，而非 startswith 前缀
        """
        import shlex

        with self._lock:
            cmd = command.strip()
            cmd_lower = cmd.lower()

            # 1. 黑名单正则
            for pat in self._blacklist_patterns:
                if pat.search(cmd_lower):
                    return False, f"命中黑名单规则: {pat.pattern}"

            # 2. 禁止 shell 元字符（防止命令拼接注入）
            # 注意：白名单内均为单条命令，不需要管道/重定向/命令分隔
            dangerous_chars = [";", "&", "|", "`", "$", ">", "<", "\n", "\r"]
            for ch in dangerous_chars:
                if ch in cmd:
                    return False, f"命令包含禁止的 shell 元字符: {ch!r}"

            # 3. shlex 解析，取命令名 + 可选子命令精确匹配白名单
            try:
                tokens = shlex.split(cmd, posix=True)
            except ValueError as e:
                return False, f"命令解析失败: {e}"
            if not tokens:
                return False, "空命令"

            cmd_name = tokens[0].lower()
            # 白名单可能含 "git status" 这种带子命令的项
            allowed = cmd_name in self._cmd_whitelist
            if not allowed and len(tokens) >= 2:
                cmd_with_sub = f"{cmd_name} {tokens[1].lower()}"
                allowed = cmd_with_sub in self._cmd_whitelist

            if not allowed:
                return False, f"命令不在白名单中。当前白名单: {sorted(self._cmd_whitelist)}"

            return True, "ok"

    # ---------- 文件边界 ----------

    @staticmethod
    def resolve_within_root(target: str, root: Path) -> Path:
        """将目标路径解析为绝对路径，并确保位于 root 下。"""
        target_path = Path(target)
        if not target_path.is_absolute():
            target_path = root / target_path
        target_path = target_path.resolve()
        root = root.resolve()
        if not str(target_path).startswith(str(root)):
            raise PermissionError(f"路径越界: {target_path} 不在 {root} 内")
        return target_path


# 全局单例
_permission_cache_instance: PermissionCache | None = None
_permission_cache_lock = threading.Lock()


def get_permission_cache() -> PermissionCache:
    global _permission_cache_instance
    if _permission_cache_instance is None:
        with _permission_cache_lock:
            if _permission_cache_instance is None:
                _permission_cache_instance = PermissionCache()
    return _permission_cache_instance
