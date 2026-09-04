# 使用说明

## 一次启动

完成一次性依赖安装后，在仓库根目录运行 <code>./start.ps1</code>。

脚本会启动后端和前端、等待 <code>http://127.0.0.1:8001/health</code> 与 <code>http://127.0.0.1:3000</code> 可用，并自动在系统浏览器打开工作台。按任意键会停止这两个本次启动的进程。

在 ChatGPT 桌面版的 Codex 中，使用 <code>./start.ps1 -NoBrowser</code> 避免自动打开 Chrome，然后在当前 Codex 对话中使用 <code>@Browser</code> 打开 <code>http://127.0.0.1:3000</code>。内置浏览器会把这个本地页面作为与对话共享的审查视图。Codex CLI、IDE 或没有 Browser 能力的环境可直接复制该地址到普通浏览器。

## 审查与防护

1. 安装并启用 <code>plugin/</code> 中的 Codex 插件。
2. 在 Codex 中执行任务；会话、工具调用、失败和风险事件会实时出现在工作台。
3. 对磁盘格式化、物理磁盘写入、越出项目边界的递归删除和远程脚本直灌 shell，Safety Sentinel 会在 PreToolUse 阶段阻断。
4. 选择会话和事件，核对脱敏证据、确定性风险说明与执行顺序。
5. 输入具体审查意见，复制生成的修正提示并发送回 Codex。

Hook 采集是 best-effort：后端未启动、输入格式错误或请求超时不会阻断正常 Codex 任务。Safety Sentinel 的少数高风险阻断在本地 Hook 内完成，不依赖后端可用性。EvolveTrace 只展示 Hook 暴露的工程证据，不展示隐藏思维链，也不替代最终代码审查或操作系统级沙箱。

无需真实 Codex 的本地演示见 [demo.md](demo.md)。
