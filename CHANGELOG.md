# 更新日志

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

---

## [Unreleased]

### Added
- 工作台支持需修复后的新尝试准备、已保存复核展示和前后 Run 逐项比较；具体比较对持久化，支持同对重试与刷新恢复，修正执行仍由用户在新 Codex 会话完成
- 按项目展示最近记忆加载的时间、触发方式与实际返回 ID；仅保存客户端输出声明，不把界面查询或模型采用当作加载证据
- 跨项目命令分类、次数、结果与耗时统计，带证据引用的重复操作和连续失败提醒
- 可选分析窗口、忽略/静音、人工确认审计记忆及 Context 按项目回读
- 有界后台执行元数据补齐、持久化退避重试和补齐状态
- SSE 重连与队列溢出后的已入库历史恢复
- Task / Context Snapshot / Context Receipt / Run 绑定、确定性评估与人工复核
- 合成修正前后 Run 对比、单调证据等级和单进程本地工作台
- 统一 EvolveTrace 插件及独立安装的 EvolveTrace Context 组件

### Changed
- 项目审计记忆改为可见区域，展示空态、读取失败、人工确认时间和来源会话；切换项目时不展示其他项目的异步结果
- README 按使用场景、首次接入与入口边界重写，同步官网说明；区分工作台功能、CLI/API 入口和路线图
- 上下文发行包与 Python 模块统一为 `evolvetrace-context` / `evolvetrace_context`；CLI 保持 `aictx`
- 官网、README 与下载版本对齐；明确通用回归重放和原生分析弹窗仍为计划
- 应用采用 Apache-2.0，Context 组件保留 MIT 与原始许可声明

### Fixed
- 修复 blocked 复核后 Task 状态无法读取、needs_fix 无法重新激活，以及非活动 Task 的旧租约仍自动绑定新会话的问题
- Run 列表不再将已绑定 Session 等同于证据就绪，仅展示已记录的运行状态
- Task / Run / Session 选择与评估目标保持一致，切换时隔离旧评估与备注，后台事件不再抢占当前审查对象
- Context 的任务提交与审计请求共用有界 loopback JSON 传输，统一拒绝重定向、环境代理和超限响应
- 项目切换的 `aictx load` 沿用已显式启用的审计记忆回读配置；未配置仍离线，显式地址优先
- 未接入的验收条件不再漏检；必需项与缺项历史快照不能被接受
- 风险失败判断复用结构化结果，修正自由文本误报与失败事件漏报
- 时间线按会话和调用 ID 配对，支持失败完成、乱序开始及事件去重
- Hook 上报前补齐 `token=` 脱敏，并用共享合成合同验证两层处理
- 本地安全拒绝先于遥测返回，防止无效上报地址或采集异常导致拒绝结果丢失
- 增加依赖告警检查及开发依赖输入边界测试，保留原始告警并只接受已复核的精确范围
- 升级 Next.js 至 16.4.1，并提高 AnyIO 的最低修复版本；同步 Node 22 构建环境
- 执行结果未知、取消或冲突时不推断为成功；过期验证不能通过 required 门禁
- 官网拒绝从脏工作区构建，避免新宣传文案配旧源码下载
- 演示文档改用独立端口并指定种子数据库，不再引导默认服务读取另一组数据

### Removed
- 旧 audit-only 插件清单、重复 Hook 配置和后端独立 Dockerfile；统一插件继续打包原采集与安全实现，容器使用根目录 Dockerfile
- 重复忽略规则及已不存在的后端模块格式化配置
- Context 内未接入生产流程的 ExecutionProfile 模型及专属测试，后端执行环境模型保留；移除未使用的回执查询前端封装
- 未调用的前端 API 封装和未接入服务的文件存在性评估实现；后端 API 与未接入验收条件的阻断门禁保留
- 新工作区不再生成加载链路未消费的 `CURRENT.md` 模板；已有用户文件保留
- 未被引用的旧会话列表、汇总组件、后端地址常量和 Agent 执行器任务模板；当前任务工作台与 API 配置继续使用

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
