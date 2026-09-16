# 运行与部署

EvolveTrace 以一个 FastAPI 本地服务提供 API、SSE 和已构建的工作台，不需要模型账号或 API Key。

## 用户模式（单进程）

```powershell
./scripts/build_static_ui.ps1
./start.ps1
```

访问 `http://127.0.0.1:8001`。`-NoBrowser` 会只打印这个 URL，便于用 Codex Browser 打开。

## 本地开发

```powershell
cd backend
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements-dev.txt
venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8001
```

开发时可另开终端运行 Next.js 热更新：

```powershell
npm install
npm run dev
```

访问 `http://localhost:3000`。审计 API 默认只接受 loopback 请求。

## Docker

```powershell
docker compose up --build
```

审计数据库写入 Docker volume。可通过 `ALLOWED_ORIGINS` 调整本地前端来源；不要把后端端口暴露到不可信网络。

## 演示数据

```powershell
cd backend
venv\Scripts\python.exe scripts\seed_demo.py
```

脚本回放 `tests/fixtures/codex_hook_session.json`，与自动化测试使用同一事件协议。
