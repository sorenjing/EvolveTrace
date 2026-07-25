"""
截图工具：捕获当前屏幕并保存，返回图片路径或 base64（供 LLM 视觉推理使用）。
仅在检测到 LLM 支持视觉输入时启用。无 GUI 环境自动降级返回提示。
"""
import base64
import os
import time
from pathlib import Path

try:
    import pyautogui
    from PIL import Image
    PYAUTOGUI_AVAILABLE = True
except Exception:
    PYAUTOGUI_AVAILABLE = False

from config import SCREENSHOT_DIR
from logger import get_logger

log = get_logger("tools.screenshot")


def _is_headless() -> bool:
    """检测当前是否为无 GUI 环境（无法截屏）。

    Windows 没有真正可靠的 headless 检测 API，GetDesktopWindow() 返回的是
    桌面窗口句柄常量（通常非零），不能用于判断。这里改用
    GetSystemMetrics(SM_REMOTESESSION)=0x1000 + 进程会话ID组合判断，
    无法确定时返回 False，让截图函数自身异常兜底。
    """
    # Linux: 无 DISPLAY 环境变量
    if os.name == "posix" and not os.environ.get("DISPLAY"):
        return True
    # Windows: 通过 SessionId 判断（Session 0 通常是服务会话，无桌面）
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            # SM_REMOTESESSION = 0x1000，返回非零表示当前是远程会话（有桌面）
            # 不能仅凭此判断，还需查 ProcessIdToSessionId
            kernel32 = ctypes.windll.kernel32
            process_id = ctypes.windll.kernel32.GetCurrentProcessId()
            session_id = wintypes.DWORD()
            if not kernel32.ProcessIdToSessionId(process_id, ctypes.byref(session_id)):
                # 调用失败，无法判断，交给截图函数兜底
                return False
            # Session 0 通常是服务会话（无桌面交互），其他会话通常有桌面
            if session_id.value == 0:
                return True
        except Exception:
            # 探测失败，不轻易返回 True（会误禁用截图），交给截图函数兜底
            return False
    return False


def screenshot(save_path: str = "", return_base64: bool = True) -> str:
    """
    截取当前屏幕。
    - save_path: 可选自定义保存路径（相对于 screenshots/）
    - return_base64: True 返回 base64 数据 URL，False 返回本地路径
    """
    if not PYAUTOGUI_AVAILABLE:
        return "[错误] 截图依赖未安装（pyautogui / PIL），请执行: pip install pyautogui pillow"

    if _is_headless():
        log.warning("当前为无 GUI 环境，截图不可用")
        return "[错误] 当前为无 GUI 环境（headless），截图不可用。请在有桌面环境的机器上运行。"

    try:
        img = pyautogui.screenshot()
        if not save_path:
            save_path = f"screenshot_{int(time.time())}.png"
        # 限制保存路径必须在 SCREENSHOT_DIR 内，防止 ../ 穿越
        base = SCREENSHOT_DIR.resolve()
        target = (base / save_path).resolve()
        try:
            if not target.is_relative_to(base):
                return f"[错误] 截图路径越界: {save_path}"
        except AttributeError:
            if base not in target.parents and target != base:
                return f"[错误] 截图路径越界: {save_path}"
        target.parent.mkdir(parents=True, exist_ok=True)
        img.save(target)

        if return_base64:
            with open(target, "rb") as f:
                data = base64.b64encode(f.read()).decode("utf-8")
            return f"data:image/png;base64,{data}"
        return str(target)
    except Exception as e:
        log.error("截图失败: %s", e)
        return f"[错误] 截图失败: {e}"
