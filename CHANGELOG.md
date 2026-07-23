# 更新日志

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

---

## [Unreleased]

### Added
- 任务模板首页（6 个高频模板一键填入）
- 暗黑模式切换（class 策略，避免 FOUC）
- Timeline 状态色徽章、步骤折叠、长内容折叠
- 错误边界（ErrorBoundary）全局捕获
- 响应式布局（移动端适配）
- **LLM 流式输出**：`LLMClient.chat_stream()` 逐 token yield，支持前端打字效果
- **todo 结构化字段**：system prompt 约束模型输出 `todos` 数组，上下文压缩后可恢复进度

### Changed
- **License**：由 MIT 改为 **PolyForm Noncommercial 1.0.0**（禁止未授权商用）
- API Key 配置面板增加安全警告提示
- **LLM max_tokens 参数化**：从硬编码 2048 改为可配置参数（默认 4096）
- **LLM 超时分级**：连接超时 10s + 读取超时 120s（原统一 120s）

### Fixed
- **视觉模型误判**：`capability.py` 移除 `glm-4-flash`（非视觉模型），保留 `glm-4v`（视觉版）
- **todo 提取脆弱**：`extract_todos` 从纯字符串匹配升级为结构化字段优先 + 文本兜底，按内容去重

### Improved
- 前端响应式与移动端体验
- Timeline 错误步骤可视化

---

## [0.1.0] - 2026-06-28

### Added
- **核心内核**：自研 ReAct 循环 AgentKernel，支持思考-行动-观察多步推理
- **可视化 Timeline**：实时展示 Agent 每一步思考、工具调用、观察结果
- **工具系统**：
  - 16 个内置工具（文件、代码、搜索、Web、自省等）
  - 动态自定义工具：Agent 可自行创建工具并持久化
- **安全设计**：
  - 三层命令注入防御（白名单 + 角色权限 + 路径沙箱）
  - Git 快照-验证-回滚闭环，保护 Agent 自我修改安全
  - API 鉴权（AGENT_TOKEN）
- **后端**：FastAPI + SSE 流式推送
- **前端**：Next.js 16 + React 19 + Tailwind CSS v4
- **工程化**：
  - Docker 一键部署（docker-compose）
  - GitHub Actions CI（后端 py_compile + 前端 build/lint）
  - 依赖版本锁定（requirements.txt）
  - 代码格式化（black + isort + prettier）
- **会话持久化**：Redis（可选，自动回退内存）
- **文档**：README / RUN.md / DESIGN.md / docs/usage.md

### Known Issues
- 测试覆盖率较低（仅 test_code_safety.py）
- 前端状态管理使用 useState，复杂场景下可能冗余
- 数据持久化为文件，未接入数据库

---

## 版本类型说明

- `Added`：新增功能
- `Changed`：对已有功能的变更
- `Deprecated`：即将弃用
- `Removed`：已移除
- `Fixed`：Bug 修复
- `Security`：安全相关修复
- `Improved`：体验优化（非功能变更）
