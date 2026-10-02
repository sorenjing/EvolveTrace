# EvolveTrace 项目定位

EvolveTrace 是面向 Coding Agent 的本地执行证据、评估、复核与回归 Harness。最终 diff 无法说明 Agent 收到了什么任务和上下文、实际执行了什么、验证是否通过。项目将 Task Contract、Context Snapshot、Codex Hooks 的可观察事件、确定性 Evaluation Result 和人工 Review Decision 绑定成可审查的运行记录，并支持经复核的修复前后比较。

项目现在同时提供一层窄而可验证的本地 Safety Sentinel：对于磁盘格式化、物理磁盘写入、越出项目边界的递归删除和远程脚本直灌 shell 等高置信度风险，它在 Codex PreToolUse 阶段返回拒绝；每一次拒绝仍保存为脱敏审计证据。

项目刻意保持窄边界：不执行 Agent、不调用额外 LLM、不展示隐藏思维链、不上传源代码。风险与阻断均来自可测试的确定性规则；最终接受与否由人判断。它不是完整沙箱，也不声称覆盖所有工具路径。LangChain 或 LangGraph 可以作为未来的适配、Trace 或 Eval 集成对象，但不成为核心架构依赖或通用业务 Workflow Runtime。

当前版本面向个人开发者和本地工作流。Task、Context、Run、首个确定性 Eval 与人工 Review 闭环已经实现，并提供修复前后比较及合成 fixture；通用 Regression Case 导入、导出和重放仍是后续工作。仓库提供自动化测试和无需真实 Codex 的演示；在 ChatGPT 桌面版中可通过内置 Browser 打开本地审查页面，但尚未宣称团队协作、跨 Agent 兼容或大规模性能指标。
