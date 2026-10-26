# EvolveTrace 项目定位

产品阶段、目标用户、替代方案与下一轮验证建议见[产品评审](product-review.md)。近期优先验证“任务结束后，开发者能否更快核对验收依据并决定接受或补充验证”；审查提速与需求强度仍待实测。

EvolveTrace 是面向 Coding Agent 的本地执行证据、评估、复核与回归 Harness。最终 diff 无法说明 Agent 收到了什么任务和上下文、实际执行了什么、验证是否通过。项目将 Task Contract、Context Snapshot、Codex Hooks 的可观察事件、确定性 Evaluation Result 和人工 Review Decision 绑定成可审查的运行记录，并支持经复核的修复前后比较。

项目同时提供一层窄范围的本地 Safety Sentinel：在支持的 PreToolUse Bash 事件中，针对格式化/擦除设备、直接写物理磁盘、递归删除根目录/家目录/父目录、下载内容管道给 shell 等高置信度危险模式返回拒绝。拒绝先于尽力上报；采集失败时可能缺少相应审计记录。它不覆盖所有项目边界外的删除或所有工具路径。

项目刻意保持窄边界：不执行 Agent、不调用额外 LLM、不展示隐藏思维链、不上传源代码。风险与阻断均来自可测试的确定性规则；最终接受与否由人判断。它不是完整沙箱，也不声称覆盖所有工具路径。LangChain 或 LangGraph 可以作为未来的适配、Trace 或 Eval 集成对象，但不成为核心架构依赖或通用业务 Workflow Runtime。

当前版本面向个人开发者和本地工作流。Task、Context、Run、首个确定性 Eval 与人工 Review 闭环已经实现，并提供修复前后比较及合成 fixture。本地 Run 回归草稿导出、人工冻结标签和离线证据重新评分已实现；通用回归能力扩展及 Agent 重新执行仍属后续设计范围，详见[回归说明](regression.md)。仓库提供自动化测试和无需真实 Codex 的演示；本地审查页面可在浏览器打开。团队协作、跨 Agent 兼容及大规模性能收益尚未验证。
