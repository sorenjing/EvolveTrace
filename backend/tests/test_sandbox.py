"""
权限沙箱的单元测试：命令注入防御、路径越界、角色权限。

运行方式：
    cd backend && python -m pytest tests/test_sandbox.py -v
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from auth.permissions import PermissionCache, get_permission_cache
from config import PROJECT_ROOT


@pytest.fixture
def perm() -> PermissionCache:
    """每次测试都获取新实例，避免状态污染。"""
    pc = PermissionCache()
    pc.set_role("standard")
    return pc


# ---------- 命令注入防御 ----------

class TestCommandInjection:
    """三层命令注入防御测试。"""

    def test_normal_command_allowed(self, perm: PermissionCache):
        allowed, reason = perm.check_command("npm install")
        assert allowed, f"npm install 应在白名单中: {reason}"

    def test_git_status_allowed(self, perm: PermissionCache):
        allowed, reason = perm.check_command("git status")
        assert allowed, f"git status 应在白名单中: {reason}"

    def test_unknown_command_blocked(self, perm: PermissionCache):
        allowed, reason = perm.check_command("rm -rf /")
        assert not allowed, "rm 不在白名单中，应被拦截"

    def test_semicolon_injection_blocked(self, perm: PermissionCache):
        """npm; rm -rf x 应被元字符检测拦截。"""
        allowed, reason = perm.check_command("npm; rm -rf /")
        assert not allowed, "分号是禁用元字符，应被拦截"

    def test_pipe_injection_blocked(self, perm: PermissionCache):
        allowed, reason = perm.check_command("ls | rm -rf /")
        assert not allowed, "管道符是禁用元字符，应被拦截"

    def test_ampersand_injection_blocked(self, perm: PermissionCache):
        allowed, reason = perm.check_command("npm & del /f /s *")
        assert not allowed, "& 是禁用元字符，应被拦截"

    def test_backtick_injection_blocked(self, perm: PermissionCache):
        allowed, reason = perm.check_command("echo `rm -rf /`")
        assert not allowed, "反引号是禁用元字符，应被拦截"

    def test_dollar_sign_blocked(self, perm: PermissionCache):
        allowed, reason = perm.check_command("echo $(whoami)")
        assert not allowed, "$ 是禁用元字符，应被拦截"

    def test_python_c_blocked(self, perm: PermissionCache):
        """python -c 可执行任意代码，即使 python 在白名单也应拦截。"""
        allowed, reason = perm.check_command('python -c "print(1)"')
        assert not allowed, f"python -c 应被拦截: {reason}"

    def test_node_e_blocked(self, perm: PermissionCache):
        allowed, reason = perm.check_command('node -e "console.log(1)"')
        assert not allowed, f"node -e 应被拦截: {reason}"

    def test_empty_command_blocked(self, perm: PermissionCache):
        allowed, reason = perm.check_command("")
        assert not allowed, "空命令应被拦截"

    def test_blacklist_regex_rm_rf_root(self, perm: PermissionCache):
        """即使命令名在白名单，黑名单正则应拦截。"""
        # 直接测试黑名单正则（rm -rf / 会被元字符检测先拦截，但模式本身需验证）
        allowed, reason = perm.check_command("rm -rf /")
        assert not allowed, "rm -rf / 应被拦截（黑名单或白名单）"


# ---------- 路径越界 ----------

class TestPathSandbox:

    def test_within_root(self, perm: PermissionCache):
        target = perm.resolve_within_root("backend/main.py", PROJECT_ROOT)
        assert target.is_relative_to(PROJECT_ROOT)

    def test_absolute_within_root(self, perm: PermissionCache):
        abs_path = str(PROJECT_ROOT / "backend" / "main.py")
        target = perm.resolve_within_root(abs_path, PROJECT_ROOT)
        assert target.exists() or target.is_relative_to(PROJECT_ROOT)

    def test_path_traversal_blocked(self, perm: PermissionCache):
        """../ 路径遍历应被拦截。"""
        with pytest.raises(PermissionError, match="越界"):
            perm.resolve_within_root("../etc/passwd", PROJECT_ROOT)

    def test_absolute_outside_blocked(self, perm: PermissionCache):
        """绝对路径越界应被拦截。"""
        with pytest.raises(PermissionError, match="越界"):
            perm.resolve_within_root("/etc/passwd", PROJECT_ROOT)

    def test_prefix_sibling_escape_blocked(self, perm: PermissionCache):
        """EvolveLab_evil 这类共享前缀的兄弟目录应被拦截。"""
        sibling = PROJECT_ROOT.parent / f"{PROJECT_ROOT.name}_evil" / "x.txt"
        with pytest.raises(PermissionError, match="越界"):
            perm.resolve_within_root(str(sibling), PROJECT_ROOT)


# ---------- 角色权限 ----------

class TestRolePermissions:

    def test_default_role_is_standard(self):
        pc = PermissionCache()
        assert pc.get_role() == "standard"

    def test_switch_to_admin(self, perm: PermissionCache):
        perm.set_role("admin")
        assert perm.get_role() == "admin"

    def test_switch_to_readonly(self, perm: PermissionCache):
        perm.set_role("readonly")
        assert perm.get_role() == "readonly"

    def test_invalid_role_raises(self, perm: PermissionCache):
        with pytest.raises(ValueError, match="未知角色"):
            perm.set_role("superadmin")

    def test_standard_can_write_file(self, perm: PermissionCache):
        config = perm.get_role_config("standard")
        assert config["allow_file_write"] is True

    def test_standard_cannot_delete_file(self, perm: PermissionCache):
        config = perm.get_role_config("standard")
        assert config["allow_file_delete"] is False

    def test_readonly_cannot_write(self, perm: PermissionCache):
        config = perm.get_role_config("readonly")
        assert config["allow_file_write"] is False

    def test_admin_can_delete(self, perm: PermissionCache):
        config = perm.get_role_config("admin")
        assert config["allow_file_delete"] is True


# ---------- 白名单管理 ----------

class TestWhitelist:

    def test_add_command(self, perm: PermissionCache):
        perm.add_whitelist("docker ps")
        allowed, _ = perm.check_command("docker ps")
        assert allowed, "docker ps 添加后应被允许"

    def test_remove_command(self, perm: PermissionCache):
        perm.add_whitelist("docker ps")
        perm.remove_whitelist("docker ps")
        allowed, _ = perm.check_command("docker ps")
        assert not allowed, "docker ps 移除后应被拦截"

    def test_add_then_check(self, perm: PermissionCache):
        """添加命令后立即可用。"""
        perm.add_whitelist("custom_cmd")
        allowed, reason = perm.check_command("custom_cmd")
        assert allowed, f"custom_cmd 应在白名单中: {reason}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])