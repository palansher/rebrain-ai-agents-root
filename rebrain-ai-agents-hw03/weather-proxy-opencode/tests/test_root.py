"""Tests for the root and health endpoints."""

import httpx


async def test_root_returns_service_info(client: httpx.AsyncClient) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "weather-proxy"
    assert body["version"] == "0.1.0"
    assert body["docs"] == "/docs"
    assert {"/health", "/weather", "/forecast"} <= set(body["endpoints"])


async def test_favicon_does_not_return_404(client: httpx.AsyncClient) -> None:
    response = await client.get("/favicon.ico")

    assert response.status_code == 204
