# 运行与部署

EvolveTrace 以一个 FastAPI 本地服务提供 API、SSE 和已构建的工作台，不需要模型账号或 API Key。

日常操作见 [中文使用手册](docs/usage.md)，服务、Hook、Run 和 Evaluation 的分层检查见 [观测手册](docs/observability.md)。

## 用户模式（单进程）

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

推荐使用上面的本机安装流程。Docker 尚未通过完整的 Hook 与审查验收；桥接网络下
请求来源会改变，可能被 loopback API 拒绝。不要扩大 API 来源或向公网暴露端口来绕过限制。

```powershell
docker compose up --build
```

审计数据库写入 Docker volume。Compose 默认仅在 `127.0.0.1:8001` 发布服务；可通过 `ALLOWED_ORIGINS` 调整本地前端来源。

## 演示数据

```powershell
cd backend
venv\Scripts\python.exe scripts\seed_demo.py
```

脚本回放 `tests/fixtures/codex_hook_session.json`，与自动化测试使用同一事件协议。
