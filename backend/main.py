"""FastAPI entry point for the local EvolveTrace audit service."""

import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from api.routes import router


STATIC_UI_DIR = Path(os.getenv("EVOLVETRACE_STATIC_UI_DIR", Path(__file__).resolve().parent / "static"))


def create_app(static_ui_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="EvolveTrace Backend", version="0.1.0")
    origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    app.add_middleware(CORSMiddleware, allow_origins=[item.strip() for item in origins.split(",") if item.strip()], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    app.include_router(router, prefix="/api")
    @app.get("/health")
    async def health(): return {"status": "ok"}
    directory = static_ui_dir or STATIC_UI_DIR
    if directory.joinpath("index.html").is_file(): app.mount("/", StaticFiles(directory=directory, html=True), name="workbench")
    else:
        @app.get("/", include_in_schema=False)
        async def static_ui_not_built(): return PlainTextResponse("Static UI has not been built. Run scripts/build_static_ui.ps1 first.", status_code=404)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run("main:app", host=host, port=port, reload=True)
