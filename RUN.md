# 运行与部署

EvolveTrace 由本地 FastAPI 审计服务和 Next.js 审查界面组成，不需要模型账号或 API Key。

## 本地开发

```powershell
cd backend
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements-dev.txt
venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8001
```

另开终端：

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
