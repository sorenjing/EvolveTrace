"""
自定义工具动态加载器。
负责扫描 custom/ 目录下的 .py 文件，动态 import 并注册到 TOOLS 字典。
工具文件需遵循约定：模块级定义 TOOL_NAME、TOOL_DESCRIPTION、TOOL_ARGS 和 run(**kwargs) -> str。
"""
import importlib.util
import threading
from pathlib import Path
from typing import Callable, Any

from config import PROJECT_ROOT

CUSTOM_DIR = PROJECT_ROOT / "backend" / "tools" / "custom"
CUSTOM_DIR.mkdir(parents=True, exist_ok=True)

# 自定义工具元信息：name -> {description, args, file}
_custom_meta: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def _load_module(file_path: Path) -> Any:
    """从文件路径动态加载 Python 模块。"""
    module_name = f"_custom_tool_{file_path.stem}"
    # 加载前先做 AST 安全审查，防止绕过 create_tool 的恶意文件被执行
    from .code_safety import audit_code
    code = file_path.read_text(encoding="utf-8", errors="replace")
    is_safe, reasons = audit_code(code)
    if not is_safe:
        raise RuntimeError(f"代码安全审查未通过: {'; '.join(reasons)}")

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块: {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_all_custom_tools(
    tools_dict: dict[str, Callable[..., str]],
    tools_meta: list[dict[str, Any]],
) -> int:
    """
    启动时调用：扫描 custom/ 目录，加载所有自定义工具到 tools_dict 和 tools_meta。
    返回成功加载的工具数量。
    """
    loaded = 0
    for py in CUSTOM_DIR.glob("*.py"):
        if py.name == "__init__.py":
            continue
        try:
            mod = _load_module(py)
            name = getattr(mod, "TOOL_NAME", None)
            desc = getattr(mod, "TOOL_DESCRIPTION", "")
            args = getattr(mod, "TOOL_ARGS", [])
            run_fn = getattr(mod, "run", None)
            if not name or not callable(run_fn):
                continue
            tools_dict[name] = run_fn
            tools_meta.append({
                "name": name,
                "description": desc,
                "args": list(args),
                "custom": True,
            })
            with _lock:
                _custom_meta[name] = {
                    "description": desc,
                    "args": list(args),
                    "file": str(py.relative_to(PROJECT_ROOT)),
                }
            loaded += 1
        except Exception as e:
            # 加载失败不阻塞其他工具
            print(f"[registry] 加载自定义工具失败 {py.name}: {e}")
    return loaded


def register_tool(
    name: str,
    description: str,
    args: list[str],
    code: str,
    tools_dict: dict[str, Callable[..., str]],
    tools_meta: list[dict[str, Any]],
) -> tuple[bool, str]:
    """
    创建并注册一个自定义工具。
    1. 写入 custom/{name}.py
    2. 动态加载并注册到 tools_dict / tools_meta
    返回 (success, message)。
    """
    # 名称校验：只允许小写字母、数字、下划线
    if not name or not name.replace("_", "").isalnum():
        return False, "工具名只能包含字母、数字、下划线"
    if not name[0].isalpha():
        return False, "工具名必须以字母开头"

    # 代码安全审查：拦截危险调用（os.system / subprocess / eval 等）
    from .code_safety import audit_code
    is_safe, reasons = audit_code(code)
    if not is_safe:
        return False, f"代码安全审查未通过: {'; '.join(reasons)}"

    file_path = CUSTOM_DIR / f"{name}.py"

    # 写入文件
    try:
        file_path.write_text(code, encoding="utf-8")
    except Exception as e:
        return False, f"写入工具文件失败: {e}"

    # 动态加载
    try:
        mod = _load_module(file_path)
        run_fn = getattr(mod, "run", None)
        if not callable(run_fn):
            return False, "工具代码缺少 run(**kwargs) 函数"

        # 校验模块声明的 TOOL_NAME 与传入 name 一致
        mod_name = getattr(mod, "TOOL_NAME", name)
        if mod_name != name:
            file_path.unlink(missing_ok=True)
            return False, f"代码中 TOOL_NAME='{mod_name}' 与注册名 '{name}' 不一致"

        # 若已存在同名工具，先移除旧元数据
        unregister_tool(name, tools_dict, tools_meta)

        tools_dict[name] = run_fn
        tools_meta.append({
            "name": name,
            "description": description,
            "args": list(args),
            "custom": True,
        })
        with _lock:
            _custom_meta[name] = {
                "description": description,
                "args": list(args),
                "file": str(file_path.relative_to(PROJECT_ROOT)),
            }
        return True, f"工具 '{name}' 已创建并注册成功"
    except Exception as e:
        # 加载失败，删除刚写的文件避免残留
        file_path.unlink(missing_ok=True)
        return False, f"工具加载失败: {e}"


def unregister_tool(
    name: str,
    tools_dict: dict[str, Callable[..., str]],
    tools_meta: list[dict[str, Any]],
) -> bool:
    """从注册表移除一个自定义工具（不删文件）。"""
    removed = False
    if name in tools_dict:
        del tools_dict[name]
        removed = True
    # 移除元数据
    for i, m in enumerate(tools_meta):
        if m.get("name") == name and m.get("custom"):
            tools_meta.pop(i)
            break
    with _lock:
        _custom_meta.pop(name, None)
    return removed


def delete_tool_file(name: str) -> tuple[bool, str]:
    """删除自定义工具文件。"""
    file_path = CUSTOM_DIR / f"{name}.py"
    if not file_path.exists():
        return False, f"工具文件不存在: {file_path.name}"
    try:
        file_path.unlink()
        return True, f"已删除工具文件 {file_path.name}"
    except Exception as e:
        return False, f"删除失败: {e}"


def list_custom_tools() -> list[dict[str, Any]]:
    """列出所有自定义工具的元信息。"""
    with _lock:
        return [
            {"name": k, **v}
            for k, v in _custom_meta.items()
        ]
