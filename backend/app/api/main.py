from contextlib import asynccontextmanager
from pathlib import Path
import secrets
import sys
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.api.routes import router
from app.api.websocket import router as websocket_router
from app.api.settings import router as settings_router
from app.core.assistant import Assistant
from app.core.config import get_settings
from app.core.exceptions import AssistantError
from app.core.orchestrator import Orchestrator
from app.llm.client import create_provider
from app.memory.store import Store
from app.tools.apps import application_tool
from app.tools.executor import ToolExecutor
from app.tools.files import FileTools
from app.tools.registry import ToolRegistry
from app.tools.system import system_tool
from app.tools.factory import create_registry


def create_app(settings=None, provider=None):
    @asynccontextmanager
    async def lifespan(app):
        config = settings or get_settings()
        llm = provider or create_provider(config)
        registry = create_registry(config)
        app.state.config = config
        app.state.token = config.api_token.get_secret_value()
        app.state.store = Store(config.data_dir / "history.sqlite3") if provider is None else None
        app.state.assistant = Assistant(Orchestrator(llm, ToolExecutor(registry), config.agent_max_steps), store=app.state.store)
        try:
            yield
        finally:
            await app.state.assistant.orchestrator.provider.aclose()
            if app.state.store:
                app.state.store.close()

    app = FastAPI(title="Desktop Assistant", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])

    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            return JSONResponse({"detail": "Origin rejected."}, status_code=403)
        public = request.url.path == "/" or request.url.path.startswith("/assets/")
        if not public:
            actual = request.headers.get("authorization", "").removeprefix("Bearer ") or request.cookies.get("assistant_session", "")
            if not secrets.compare_digest(actual.encode(), request.app.state.token.encode()):
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'"
        return response

    @app.exception_handler(AssistantError)
    async def assistant_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    app.include_router(router)
    app.include_router(settings_router)
    app.include_router(websocket_router)
    frontend = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3])) / "frontend" / "dist"
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app


app = create_app()
