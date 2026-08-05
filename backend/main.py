"""
FastAPI 入口：Agent Evolution 后端服务。
提供 SSE 流式 Agent 接口、权限管理、LLM 能力探测。
"""
import os
from dotenv import load_dotenv

# 在导入 config 之前加载 .env（默认从 backend/ 目录读取）
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from api.routes import router
from exceptions import register_exception_handlers

app = FastAPI(title="EvolveTrace Backend", version="0.1.0")
register_exception_handlers(app)

# 速率限制：默认每分钟 30 次请求/IP，防止滥用消耗 LLM 额度
limiter = Limiter(key_func=get_remote_address, default_limits=["30/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS：默认仅允许本地前端访问；生产环境通过 ALLOWED_ORIGINS 环境变量配置
_allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    # 默认仅监听 localhost，需外网访问时设置 HOST=0.0.0.0
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run("main:app", host=host, port=port, reload=True)
