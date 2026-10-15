# 更新日志

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

---

## [Unreleased]

### Added
- 跨项目命令分类、次数、结果与耗时统计，带证据引用的重复操作和连续失败提醒
- 可选分析窗口、忽略/静音、人工确认审计记忆及 Context 按项目回读
- 有界后台执行元数据补齐、持久化退避重试和补齐状态
- SSE 重连与队列溢出后的已入库历史恢复
- Task / Context Snapshot / Context Receipt / Run 绑定、确定性评估与人工复核
- 合成修正前后 Run 对比、单调证据等级和单进程本地工作台
- 统一 EvolveTrace 插件及独立安装的 EvolveTrace Context 组件

### Changed
- 上下文发行包与 Python 模块统一为 `evolvetrace-context` / `evolvetrace_context`；CLI 保持 `aictx`
- 官网、README 与下载版本对齐；明确通用回归重放和原生分析弹窗仍为计划
- 应用采用 Apache-2.0，Context 组件保留 MIT 与原始许可声明

### Fixed
- 增加依赖告警检查及开发依赖输入边界测试，保留原始告警并只接受已复核的精确范围
- 升级 Next.js 至 16.4.1，并提高 AnyIO 的最低修复版本；同步 Node 22 构建环境
- 执行结果未知、取消或冲突时不推断为成功；过期验证不能通过 required 门禁
- 官网拒绝从脏工作区构建，避免新宣传文案配旧源码下载

以下 0.1.0 记录属于早期 Agent 原型的历史。当前产品围绕外部 Coding Agent 的执行审计与复核；历史内核、模型配置和工具执行能力不属于当前版本。

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
