# 运行与部署

EvolveTrace 以一个 FastAPI 本地服务提供 API、SSE 和已构建的工作台，不需要模型账号或 API Key。

日常操作见 [中文使用手册](docs/usage.md)，服务、Hook、Run 和 Evaluation 的分层检查见 [观测手册](docs/observability.md)。

## 用户模式（单进程）

安装依赖并构建静态工作台后，可一次性启用插件自动启动：

```powershell
python ./plugin/hooks/runtime_control.py enable --runtime .
python ./plugin/hooks/runtime_control.py status
```

安装或刷新统一插件并审核当前 Hook 后，新会话会自动启动或复用本地服务。
本地插件来源选择整个 EvolveTrace 根目录，或上传 `dist/evolvetrace-plugin.zip`；
目录区别与旧版替换见[安装目录与升级](docs/consolidation.md#安装目录与升级)。
不需要每次运行启动脚本。也可以在 Codex 使用 `$control-evolvetrace` 请求开启、
暂停、恢复采集或打开工作台。开关是 Skill 控制入口，不是 Codex 原生设置按钮。

```powershell
python ./plugin/hooks/runtime_control.py pause
python ./plugin/hooks/runtime_control.py enable
python ./plugin/hooks/runtime_control.py open
```

暂停保留运行中的工作台、历史证据、Context 交付和本地命令保护，只停止后续
采集与自动启动；正在发送的事件可能完成。整个插件的停用由 Codex 管理。
偏好和自动启动日志默认位于用户目录 `~/.evolvetrace/`，独立于安装版本；
需要隔离时，Hook 与控制器都设置同一个 `EVOLVETRACE_CONTROL_DIR`。
配置损坏会暂停采集，可重新运行带 `--runtime` 的开启命令修复。
已有 `EVOLVETRACE_API_URL` 覆盖时保留该地址，地址不同则不自动启动默认服务。
当前自动启动不自动登记项目；首次项目归属仍按下文使用 `aictx audit sync`。

保留手动启动方式：

```powershell
./scripts/build_static_ui.ps1
./start.ps1
```

访问 `http://127.0.0.1:8001`。`-NoBrowser` 会只打印这个 URL，便于用 Codex Browser 打开。

在后台保持服务运行，并登记当前工作区的项目目录：

```powershell
./start.ps1 -NoBrowser -Detached
./scripts/observe.ps1 -ExpectEvidence
```

启动器向上寻找 `.aictx.toml`，也可用 `-Workspace <目录>` 指定工作区；通过
`aictx audit sync` 仅同步项目名称和路径。已运行的兼容服务会复用，不会被启动器停止。
新服务的日志与 PID 保存在忽略的 `runtime/local-service/`；没有交互输入时默认保持后台运行。
收件状态只证明本次启动收到过 Hook；历史记录、空闲和完整采集分别显示。

改动启动器后，可在 Windows 安装好后端依赖后运行 `./tests/startup_timeout.ps1`，
验证慢启动超时会清理本次创建的 venv launcher 和子进程；探针只写入忽略的 `runtime/`。

## 本地开发

```powershell
cd backend
python -m venv venv
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements-dev.txt
venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8001
```

开发时可另开终端运行 Next.js 热更新：

```powershell
npm install
npm run dev
```

访问 `http://localhost:3000`。审计 API 默认只接受 loopback 请求。

## Docker（实验性）

容器构建统一使用根目录 `Dockerfile`，同时打包后端与静态工作台；原 `backend/Dockerfile` 已移除。

推荐使用上面的本机安装流程。Docker 尚未通过完整的 Hook 与审查验收；桥接网络下
请求来源会改变，可能被 loopback API 拒绝。不要扩大 API 来源或向公网暴露端口来绕过限制。

```powershell
docker compose up --build
```

审计数据库写入 Docker volume。Compose 默认仅在 `127.0.0.1:8001` 发布服务；可通过 `ALLOWED_ORIGINS` 调整本地前端来源。

## 演示数据

按[合成数据演示](docs/demo.md)使用独立端口和演示数据库。种子脚本回放
`task_context_run.json` 与 `context_bundle_v1.json`，固定写入 `backend/.demo-*.db`；
默认服务不会自动读取这些数据库。
