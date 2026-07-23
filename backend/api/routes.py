"""
FastAPI 路由层（薄）：仅做 HTTP 转换，业务逻辑委托给 services 层。
"""
from typing import Any

from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from auth.admin import require_admin, require_agent
from services import agent_service, tool_service, admin_service, config_service
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, get_llm_config

# 速率限制器（从 main 注入，避免循环导入）
limiter = Limiter(key_func=get_remote_address)

router = APIRouter()


# ---------- 请求模型 ----------

class TaskRequest(BaseModel):
    task: str
    role: str = "standard"
    model: str = LLM_MODEL
    api_key: str = LLM_API_KEY
    base_url: str = LLM_BASE_URL


class RoleUpdate(BaseModel):
    role: str
    config: dict[str, Any] | None = None


class WhitelistUpdate(BaseModel):
    command_prefix: str
    action: str  # add | remove


class ConfigTestRequest(BaseModel):
    api_key: str = ""
    base_url: str = LLM_BASE_URL
    model: str = LLM_MODEL


# ---------- Agent 流接口 ----------

@router.post("/agent/stream")
@limiter.limit("10/minute")
async def agent_stream(request: Request, req: TaskRequest, _: None = Depends(require_agent)):
    """启动 Agent 任务，以 SSE 流式返回执行轨迹。"""
    kernel = agent_service.create_agent(
        task=req.task, role=req.role, model=req.model,
        api_key=req.api_key, base_url=req.base_url,
    )
    return StreamingResponse(
        agent_service.stream_events(kernel),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/agent/session/{session_id}")
async def get_session(session_id: str):
    """查询会话状态。"""
    return agent_service.get_session(session_id)


# ---------- 权限管理 ----------

@router.post("/admin/role", dependencies=[Depends(require_admin)])
async def set_role(body: RoleUpdate):
    return admin_service.set_role(body.role)


@router.get("/admin/role", dependencies=[Depends(require_admin)])
async def get_role():
    return admin_service.get_role()


@router.post("/admin/whitelist", dependencies=[Depends(require_admin)])
async def update_whitelist(body: WhitelistUpdate):
    return admin_service.update_whitelist(body.command_prefix, body.action)


# ---------- LLM 能力探测 ----------

@router.get("/admin/capability", dependencies=[Depends(require_admin)])
async def get_capability(model: str = LLM_MODEL):
    return admin_service.get_capability(model)


@router.post("/admin/capability", dependencies=[Depends(require_admin)])
async def set_capability(model: str, vision: bool):
    return admin_service.set_capability(model, vision)


# ---------- 沙箱清理 ----------

@router.post("/admin/cleanup", dependencies=[Depends(require_admin)])
async def run_cleanup():
    """手动触发沙箱垃圾清除。"""
    return admin_service.run_cleanup()


@router.get("/admin/cleanup", dependencies=[Depends(require_admin)])
async def cleanup_status():
    """查看可清理的垃圾文件数量（不实际删除）。"""
    return admin_service.cleanup_status()


# ---------- 工具管理 ----------

@router.get("/tools")
async def list_all_tools():
    """列出所有可用工具（内置 + 自定义），供前端展示。"""
    return tool_service.list_tools()


@router.delete("/tools/{name}")
async def delete_custom_tool(name: str):
    """删除一个自定义工具。"""
    return tool_service.delete_tool(name)


# ---------- LLM 配置测试 ----------

@router.post("/config/test")
async def test_llm_config(req: ConfigTestRequest):
    """测试 LLM 配置是否可用。"""
    return await config_service.test_config(req.api_key, req.base_url, req.model)
