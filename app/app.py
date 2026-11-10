"""FastAPI 应用创建与路由注册。"""
from contextlib import asynccontextmanager

import asyncio

from app.workers.order_scan import order_scanner
from fastapi import FastAPI, Response

from app.api import v1_router
from app.api.exception_handlers import register_exception_handlers
from app.core import ahnx_server_config


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(order_scanner.initialize)
    await asyncio.to_thread(order_scanner.scan)
    stop = asyncio.Event()
    worker = asyncio.create_task(order_scanner.run(stop))
    try:
        yield
    finally:
        stop.set()
        await worker


def create_app() -> FastAPI:
    app = FastAPI(
        lifespan=lifespan,
        title=ahnx_server_config.title,
        version=ahnx_server_config.version,
        redirect_slashes=False,
    )
    register_exception_handlers(app)
    app.include_router(v1_router)

    @app.get("/")
    async def get_version() -> dict[str, str]:
        return {"version": app.version, "title": app.title}

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Response:
        return Response(status_code=200)

    return app
