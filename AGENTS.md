<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# EvolveLab 项目开发指南

## 项目定位
EvolveLab 是一个**白盒 AI Agent 实验平台**，自研 ReAct 内核，不依赖 LangChain/AutoGen。
核心卖点：Agent 每步思考可见、工具可动态创建、安全沙箱、自我修改能力。

## 技术栈
- 前端: Next.js 16 (App Router) + React 19 + TypeScript + Tailwind CSS v4
- 后端: Python 3.10+ + FastAPI + Uvicorn
- LLM: OpenAI-compatible API（默认智谱 GLM-4-Flash）
- 通信: SSE (Server-Sent Events)

## 关键架构决策
1. **不依赖 LangChain**: 自研 ReAct 循环（kernel.py），完全控制 Prompt、工具路由、安全策略
2. **SSE 而非 WebSocket**: 单向推送足够，复杂度更低，代理/CDN 兼容性更好
3. **API Key 存前端 localStorage**: 不写后端文件，避免 .env 泄露风险
4. **三层命令注入防御**: 黑名单正则 → 元字符禁用 → shlex 白名单精确匹配
5. **Git 快照安全层**: modify-before-snapshot → verify-build → auto-rollback on failure

## 开发约定
- 后端路由层保持薄（仅 HTTP 转换），业务逻辑下沉到 services/
- 工具系统: 新增工具只需在 tools/__init__.py 的 TOOLS 和 TOOLS_META 注册
- 自定义工具: 写入 tools/custom/ 目录，重启自动加载
- 异常处理: 业务层抛 AppError 子类，全局处理器统一为 {code, message}
- 成功响应保持原格式，不破坏前端

## 安全红线
- 绝不提交 API Key、密码、密钥
- 文件操作限制在 PROJECT_ROOT 内
- 命令执行三层防御 + 白名单
- 管理接口默认仅 localhost（远程需 ADMIN_TOKEN）

## 测试策略
- 后端: pytest（目前仅 code_safety 有测试，需补充 kernel/sandbox/permissions 测试）
- 前端: 暂无测试（待补充 Playwright E2E）
- CI: .github/workflows/ci.yml 自动跑 py_compile + pytest + build + lint

## 面试重点（给维护者）
如果你要面试讲这个项目，重点准备：
1. ReAct 循环实现细节（kernel.py 的 while 循环、JSON 强制输出、死循环检测）
2. 为什么不用 LangChain（控制力、理解深度、依赖轻量）
3. 安全设计（三层命令注入防御、路径沙箱、Git 快照回滚）
4. 工具自举原理（动态 import + AST 安全审查 + 持久化）
5. SSE vs WebSocket 选择理由
6. 上下文压缩策略（保留 todo + 完成状态，不丢关键信息）
7. LLM 调用双模式（`chat()` 非流式 + `chat_stream()` 流式，`max_tokens` 参数化）
8. 视觉能力检测（模型名白名单匹配，`glm-4v` 是视觉模型，`glm-4-flash` 不是）
