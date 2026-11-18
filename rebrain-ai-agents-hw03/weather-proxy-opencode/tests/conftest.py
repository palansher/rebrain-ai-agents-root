"""Shared pytest fixtures."""

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI

from app.main import create_app


@pytest.fixture
def app() -> FastAPI:
    """A fresh application instance for every test."""
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """HTTP client that talks to the ASGI app with its lifespan running."""
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
            yield http


@pytest.fixture
def current_payload() -> dict[str, object]:
    """Minimal valid Open-Meteo response for the ``/weather`` endpoint."""
    return {
        "latitude": 41.7151,
        "longitude": 44.8271,
        "current_units": {"temperature_2m": "°C", "wind_speed_10m": "km/h"},
        "current": {"temperature_2m": 28.4, "wind_speed_10m": 12.1},
    }


@pytest.fixture
def forecast_payload() -> dict[str, object]:
    """Minimal valid Open-Meteo response for the ``/forecast`` endpoint."""
    return {
        "latitude": 41.7151,
        "longitude": 44.8271,
        "daily_units": {
            "time": "iso8601",
            "weather_code": "wmo code",
            "temperature_2m_max": "°C",
            "temperature_2m_min": "°C",
            "wind_speed_10m_max": "km/h",
        },
        "daily": {
            "time": ["2026-11-18", "2026-11-19", "2026-11-20"],
            "weather_code": [1, 3, 61],
            "temperature_2m_max": [14.2, 12.8, 9.5],
            "temperature_2m_min": [4.1, 3.4, 2.0],
            "wind_speed_10m_max": [18.5, 22.0, 30.7],
        },
    }
