"""FastAPI application factory and the ``weather-proxy`` entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI

from app.api import VERSION, router
from app.client import OpenMeteoClient
from app.config import get_settings
from app.errors import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create a single pooled HTTP client for the lifetime of the application."""
    settings = get_settings()
    http = httpx.AsyncClient(
        base_url=settings.open_meteo_base_url,
        timeout=settings.request_timeout,
    )
    app.state.settings = settings
    app.state.open_meteo = OpenMeteoClient(http, settings)
    try:
        yield
    finally:
        await http.aclose()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title="Weather Proxy",
        version=VERSION,
        summary="FastAPI proxy for the Open-Meteo API with normalized responses.",
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    app.include_router(router)
    return app


app = create_app()


def run() -> None:
    """Run the service with uvicorn (``uv run weather-proxy``)."""
    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    run()
