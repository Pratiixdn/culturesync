"""CULTURESYNC API entry point. Run: uvicorn app.main:app --reload --port 8000
 
There is no authentication: team ids are unguessable, and anyone holding one can read and edit that team.
"""
from __future__ import annotations
 
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
 
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
 
from .llm import AgentError, GeminiClient
from .qloo import MockQlooClient, QlooClient, QlooError
from .routes import DailyCap, RateLimiter, router
from .storage import LimitError, Storage
 
log = logging.getLogger("culturesync")
 
MAX_BODY_BYTES = 64 * 1024
 
 
@dataclass
class Settings:
    qloo_api_key: str = ""
    qloo_base_url: str = "https://hackathon.api.qloo.com"
    frontend_origin: str = "http://localhost:3000"
    database_url: str = "sqlite:///./culturesync.db"
    static_dir: str = ""
    qloo_rpm: int = 30  # requests per minute per IP to Qloo-backed endpoints
    max_qloo_calls: int = 40  # per analysis run
    gemini_api_key: str = ""
    agent_model: str = "gemini-flash-latest,gemini-3.5-flash,gemini-3.1-flash-lite"  # comma-separated fallbacks
    agent_daily_limit: int = 50  # agent runs per UTC day, whole server (Gemini free tier is rate limited)
    agent_rpm: int = 4  # agent runs per minute per IP
    max_agent_qloo_calls: int = 15  # per agent run
 
    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(Path(__file__).resolve().parent.parent / ".env")
        env = os.environ.get
        return cls(
            qloo_api_key=(env("QLOO_API_KEY") or "").strip(),
            qloo_base_url=env("QLOO_BASE_URL") or cls.qloo_base_url,
            frontend_origin=env("FRONTEND_ORIGIN") or cls.frontend_origin,
            database_url=env("DATABASE_URL") or cls.database_url,
            static_dir=env("STATIC_DIR") or "",
            gemini_api_key=(env("GEMINI_API_KEY") or env("GOOGLE_API_KEY") or "").strip(),
            agent_model=env("AGENT_MODEL") or cls.agent_model,
            agent_daily_limit=int(env("AGENT_DAILY_LIMIT") or cls.agent_daily_limit),
        )
 
 
def error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
    qloo = getattr(request.app.state, "qloo", None)
    meta = {"source": "local", "mode": qloo.mode if qloo else "mock"}
    return JSONResponse(status_code=status, content={"data": None, "meta": meta, "error": {"code": code, "message": message}})
 
 
def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(QlooError)
    async def qloo_error(request: Request, err: QlooError):
        return error_response(request, err.status, err.code, err.message)
 
    @app.exception_handler(AgentError)
    async def agent_error(request: Request, err: AgentError):
        return error_response(request, err.status, err.code, err.message)
 
    @app.exception_handler(LimitError)
    async def limit_error(request: Request, err: LimitError):
        return error_response(request, 409, "limit_reached", str(err))
 
    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, err: StarletteHTTPException):
        code = "not_found" if err.status_code == 404 else "http_error"
        return error_response(request, err.status_code, code, str(err.detail))
 
    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, err: RequestValidationError):
        first: dict[str, Any] = err.errors()[0] if err.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        where = f" at {field}" if field else ""
        return error_response(request, 422, "validation_error", f"Invalid input{where}: {first.get('msg', 'bad value')}.")
 
    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, err: Exception):
        log.error("unhandled %s", type(err).__name__)  # exception type only, never request data
        return error_response(request, 500, "internal_error", "Something went wrong on the server.")
 
 
def create_app(settings: Optional[Settings] = None, qloo_client: Any = None, llm_client: Any = None) -> FastAPI:
    config = settings or Settings.from_env()
    client = qloo_client or (QlooClient(config.qloo_api_key, config.qloo_base_url) if config.qloo_api_key else MockQlooClient())
 
    llm = llm_client or (GeminiClient(config.gemini_api_key, config.agent_model) if config.gemini_api_key else None)
 
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        await client.aclose()
        if llm is not None:
            await llm.aclose()
 
    app = FastAPI(title="CULTURESYNC API", version="1.0.0", lifespan=lifespan)
    app.state.qloo = client
    app.state.store = Storage(config.database_url)
    app.state.limiter = RateLimiter(config.qloo_rpm)
    app.state.max_qloo_calls = config.max_qloo_calls
    app.state.llm = llm
    app.state.agent_limiter = RateLimiter(config.agent_rpm)
    app.state.agent_cap = DailyCap(config.agent_daily_limit)
    app.state.max_agent_qloo_calls = config.max_agent_qloo_calls
 
    origins = [o.strip() for o in config.frontend_origin.split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["Content-Type"])
 
    @app.middleware("http")
    async def limit_body_size(request: Request, call_next):
        length = request.headers.get("content-length", "")
        if length.isdigit() and int(length) > MAX_BODY_BYTES:
            return error_response(request, 413, "payload_too_large", "Request body is too large.")
        return await call_next(request)
 
    register_error_handlers(app)
    app.include_router(router)
 
    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PATCH", "DELETE"], include_in_schema=False)
    async def unknown_api_route(path: str):
        raise HTTPException(404, "Unknown API route.")
 
    # serve the exported Next.js site from the same origin
    web_dir = Path(config.static_dir) if config.static_dir else Path(__file__).resolve().parents[2] / "frontend" / "out"
    if web_dir.is_dir():
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
    return app
 
 
app = create_app()