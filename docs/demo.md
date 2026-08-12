# EvolveTrace Demo

## 本地演示

1. 在一个终端启动后端：`cd backend; venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8001`。
2. 在第二个终端启动前端：`npm run dev`。
3. 在第三个终端写入演示数据：`cd backend; venv\Scripts\python.exe scripts\seed_demo.py`。
4. 打开 `http://localhost:3000` 并刷新页面。
5. 选择 `demo-evolvetrace-session` 会话，点击时间线中的高风险 Bash 事件。
6. 在右侧事件详情核对脱敏后的证据、风险说明和工具输入。
7. 输入审查意见，例如“先展示 diff，再运行 auth 相关测试”，然后点击“复制修复提示”。

## 面试讲解顺序

先说明问题：Coding Agent 的最终结果不等于可审查的执行过程。然后演示事件如何从 Codex Hook 进入本地 API、SQLite 和 SSE 页面；最后展示风险规则如何把危险命令和失败验证转成具体的审查动作。

## 真实 Codex 流程

将 `plugin/` 作为本地插件安装并启用后，在任意项目运行一次 Codex 任务。启动 EvolveTrace 后端，页面会自动接收支持的本地 Hook 事件。Hook 只发送脱敏数据，后端关闭时不会阻断任务。