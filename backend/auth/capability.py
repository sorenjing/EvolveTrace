"""
LLM 能力检测：判断当前模型是否支持图片/视觉输入，从而决定 Agent 是否启用截图工具。
"""
import threading
from typing import Set


class LLMCapability:
    """
    维护当前使用模型的能力标签。
    由于模型能力相对静态，通常在初始化时探测或根据模型名推断，
    运行期间可手动覆盖。
    """

    # 已知支持视觉的模型名子串（小写）
    # 注意：必须是"视觉版本"的精确标识，不能误匹配同名的非视觉版本
    # 例如 glm-4-flash 不是视觉模型，glm-4v 才是
    KNOWN_VISION_MODELS: Set[str] = {
        "gpt-4o", "gpt-4-turbo", "gpt-4-vision",
        "claude-3", "claude-3.5",  # claude-3-5 改为 claude-3.5（点号版本）
        "gemini-1.5", "gemini-pro-vision",
        "qwen-vl", "qwen2-vl",
        "moonshot-v1-vision",
        "glm-4v",           # 智谱 GLM-4V（注意 v 后缀）才是视觉模型
        "glm-4-plus-v",     # glm-4-plus 的视觉版（如存在）
        # 移除 glm-4-flash：它不是视觉模型，glm-4v 才是
    }

    def __init__(self, model_name: str = ""):
        self._lock = threading.Lock()
        self._model_name = model_name.lower()
        self._vision: bool | None = None  # None 表示未探测

    def detect(self) -> bool:
        """基于模型名推断是否支持视觉。"""
        with self._lock:
            if self._vision is not None:
                return self._vision
            self._vision = any(v in self._model_name for v in self.KNOWN_VISION_MODELS)
            return self._vision

    def force_set(self, vision: bool) -> None:
        """手动覆盖视觉能力判定。"""
        with self._lock:
            self._vision = vision

    @property
    def supports_vision(self) -> bool:
        return self.detect()


# 全局单例缓存：按 model_name 复用实例，确保 force_set 跨模块生效
_capability_instances: dict[str, "LLMCapability"] = {}
_capability_instances_lock = threading.Lock()


def get_llm_capability(model_name: str = "") -> LLMCapability:
    """获取指定模型的能力探测单例（按 model_name 缓存）。"""
    key = model_name.lower()
    inst = _capability_instances.get(key)
    if inst is None:
        with _capability_instances_lock:
            inst = _capability_instances.get(key)
            if inst is None:
                inst = LLMCapability(model_name)
                _capability_instances[key] = inst
    return inst
