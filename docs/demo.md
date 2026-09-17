# EvolveTrace Demo

## 本地演示

1. 运行 `./scripts/build_static_ui.ps1`，再运行 `./start.ps1`。
2. 在另一个终端写入演示数据：`cd backend; venv\Scripts\python.exe scripts\seed_demo.py`。
3. 打开 `http://127.0.0.1:8001` 并刷新页面。
4. 选择 synthetic Task，查看 Context Snapshot、Run 和 `demo-session` 证据。
5. 在 Evidence Evaluation 面板运行确定性评估，核对 criterion 状态与 evidence refs。
6. 对缺少验证命令的首次运行记录 `needs_fix`，补齐验证后对第二次运行记录 `accepted`。
7. 比较两次 Run；只有经过人工复核的修正运行才把 Context Receipt 推进到 `effective`。

## 已实现与路线图

Task & Context 已经实现；M0.4 首个纵向切片也已实现 Context Freshness、Repository Scope、Verification、人工 Review Decision 与修复前后比较。通用 Regression Harness、更多 Evaluator 和 LLM Judge 仍是后续路线图。

## 面试讲解顺序

先说明问题：Coding Agent 的最终 diff 不等于可验证结果。然后演示结构化验收条件如何连接 Hook 事件、命令退出码和修改范围；最后展示第一次缺证据被退回、第二次补齐证据获人工接受，以及为什么单次成功不能自动证明 `effective`。

## 真实 Codex 流程

将 `plugin/` 作为本地插件安装并启用后，在任意项目运行一次 Codex 任务。启动 EvolveTrace 后端，页面会自动接收支持的本地 Hook 事件。Hook 只发送脱敏数据，后端关闭时不会阻断任务。
