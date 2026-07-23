import os
from pathlib import Path

# 项目根目录（限制文件操作范围）
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# LLM 配置：从环境变量读取，避免敏感信息硬编码进仓库
# 本地开发请在 backend/ 下创建 .env 并填入真实值（.env 已被 .gitignore 忽略）
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
LLM_MODEL = os.getenv("LLM_MODEL", "glm-4-flash")

# Agent 配置
MAX_STEPS = int(os.getenv("MAX_STEPS", "15"))

# Agent 流接口鉴权 token（为空则不鉴权；设置后 /api/agent/stream 需携带 X-Agent-Token）
AGENT_TOKEN = os.getenv("AGENT_TOKEN", "")

# 会话持久化：Redis URL（为空则用内存 dict，适合本地开发）
REDIS_URL = os.getenv("REDIS_URL", "")

# 截图保存目录
SCREENSHOT_DIR = PROJECT_ROOT / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

# 配置优先级：前端请求参数 > 环境变量 > 默认值
def get_llm_config(api_key: str = "", base_url: str = "", model: str = ""):
    """获取 LLM 配置，按优先级选择来源"""
    return {
        "api_key": api_key or LLM_API_KEY,
        "base_url": base_url or LLM_BASE_URL,
        "model": model or LLM_MODEL,
    }
