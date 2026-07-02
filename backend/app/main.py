"""FastAPI app factory + lifespan."""
from __future__ import annotations

import platform
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app import __version__
from app.core.config import get_settings
from app.core.db import db_ping, dispose_engine
from app.core.exceptions import install_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import InternalIPMiddleware, MetricsMiddleware, RequestIDMiddleware
from app.core.redis import close_redis, redis_ping

# psycopg (langgraph-checkpoint-postgres) requires SelectorEventLoop on Windows.
# uvicorn's default on Windows is ProactorEventLoop which psycopg rejects.
# Set the policy unconditionally before any loop is created.
if platform.system() == "Windows":
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

log = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = get_settings()
    log.info(
        "app.start",
        version=__version__,
        env=settings.app_env,
        log_level=settings.log_level,
    )
    # Soft-touch DB + Redis on boot (best-effort).
    log.info("deps.probe", db=await db_ping(), redis=await redis_ping())

    # 023: Warm checkpointer connection pool (best-effort, non-fatal).
    from app.agents.checkpointer import preheat as checkpointer_preheat

    await checkpointer_preheat()

    try:
        yield
    finally:
        from app.agents.checkpointer import close_checkpointer

        await close_checkpointer()
        await close_redis()
        await dispose_engine()
        log.info("app.stop")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="InterCraft API",
        version=__version__,
        description="InterCraft — 面试工坊 backend",
        lifespan=lifespan,
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json",
    )

    # CORS — explicit list from settings.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
    )

    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(InternalIPMiddleware)

    install_exception_handlers(app)

    @app.get("/healthz")
    async def healthz() -> JSONResponse:
        db_ok = await db_ping()
        redis_ok = await redis_ping()
        ok = db_ok and redis_ok
        return JSONResponse(
            status_code=200 if ok else 503,
            content={
                "status": "ok" if ok else "down",
                "db": "ok" if db_ok else "down",
                "redis": "ok" if redis_ok else "down",
                "version": __version__,
            },
        )

    @app.get("/metrics")
    async def metrics() -> JSONResponse:
        return JSONResponse(content=generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)

    # Versioned router
    from app.api.v1 import router as v1_router

    app.include_router(v1_router, prefix=settings.api_v1_prefix)

    # Internal router (no auth — guarded by InternalIPMiddleware)
    from app.api.v1.internal import router as internal_router

    app.include_router(internal_router, prefix=f"{settings.api_v1_prefix}/internal")

    # Phase 3: WebSocket endpoints
    from app.api.v1.ws.interview import router as interview_ws_router
    from app.modules.locks.ws_handler import router as locks_ws_router

    app.include_router(locks_ws_router, prefix=settings.api_v1_prefix)
    app.include_router(interview_ws_router, prefix=settings.api_v1_prefix)
    # 032: Resume v2 SSE stream (GET /api/v1/v2/resumes/events)
    from app.api.v1.ws.resume_v2 import router as resume_v2_ws_router

    app.include_router(resume_v2_ws_router, prefix=settings.api_v1_prefix)

    # 033: PM dashboard + badcase router placeholders (T022). Real handlers
    # land in US1 (pm_dashboard) and US8 (badcases). Placeholder routes
    # expose a single GET /health liveness endpoint per module so the
    # routers can be probed before the user-story implementations ship.
    from app.modules.badcases.api import router as badcases_router
    from app.modules.pm_dashboard.api import router as pm_dashboard_router

    app.include_router(
        pm_dashboard_router,
        prefix=f"{settings.api_v1_prefix}/pm-dashboard",
        tags=["pm-dashboard"],
    )
    app.include_router(
        badcases_router,
        prefix=f"{settings.api_v1_prefix}/badcases",
        tags=["badcases"],
    )

    # 039 B1: admin console observability (Log Center backend foundation).
    # Mounted at /api/v1/admin-console/observability — 7 endpoints covering
    # tag CRUD, replay, diff, and node IO pagination.
    from app.modules.admin_console.api import router as admin_console_router

    app.include_router(
        admin_console_router,
        prefix=f"{settings.api_v1_prefix}/admin-console/observability",
        tags=["admin-console"],
    )

    return app


app = create_app()


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
