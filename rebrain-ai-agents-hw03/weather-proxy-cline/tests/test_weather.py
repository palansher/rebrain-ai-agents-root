"""Tests for the ``/weather`` endpoint."""

import httpx
import pytest
from pytest_httpx import HTTPXMock


async def test_weather_returns_normalized_payload(
    client: httpx.AsyncClient,
    httpx_mock: HTTPXMock,
    current_payload: dict[str, object],
) -> None:
    httpx_mock.add_response(json=current_payload)

    response = await client.get("/weather", params={"latitude": 41.7151, "longitude": 44.8271})

    assert response.status_code == 200
    assert response.json() == {
        "latitude": 41.7151,
        "longitude": 44.8271,
        "temperature": 28.4,
        "wind_speed": 12.1,
        "source": "open-meteo",
    }

    upstream = httpx_mock.get_requests()[0]
    assert upstream.url.path == "/v1/forecast"
    assert upstream.url.params["latitude"] == "41.7151"
    assert upstream.url.params["longitude"] == "44.8271"
    assert upstream.url.params["current"] == "temperature_2m,wind_speed_10m"


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"latitude": 100, "longitude": 44.8271}, "latitude"),
        ({"latitude": -91, "longitude": 44.8271}, "latitude"),
        ({"latitude": 41.7151, "longitude": 181}, "longitude"),
        ({"longitude": 44.8271}, "latitude"),
        ({"latitude": 41.7151}, "longitude"),
    ],
)
async def test_weather_rejects_invalid_parameters(
    client: httpx.AsyncClient,
    params: dict[str, float],
    field: str,
) -> None:
    response = await client.get("/weather", params=params)

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "invalid_request"
    assert field in {detail["field"] for detail in body["details"]}


async def test_weather_reports_timeout_with_url(
    client: httpx.AsyncClient,
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_exception(httpx.ReadTimeout("timed out"))

    response = await client.get("/weather", params={"latitude": 41.7151, "longitude": 44.8271})

    assert response.status_code == 504
    body = response.json()
    assert body["error"] == "upstream_timeout"
    assert body["url"].startswith("https://api.open-meteo.com/v1/forecast")


async def test_weather_reports_unreachable_upstream(
    client: httpx.AsyncClient,
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_exception(httpx.ConnectError("connection refused"))

    response = await client.get("/weather", params={"latitude": 41.7151, "longitude": 44.8271})

    assert response.status_code == 502
    assert response.json()["error"] == "upstream_unavailable"


async def test_weather_reports_upstream_error_status(
    client: httpx.AsyncClient,
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(status_code=500, json={"reason": "boom"})

    response = await client.get("/weather", params={"latitude": 41.7151, "longitude": 44.8271})

    assert response.status_code == 502
    body = response.json()
    assert body["error"] == "upstream_error"
    assert body["upstream_status"] == 500


async def test_weather_rejects_non_json_response(
    client: httpx.AsyncClient,
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(content=b"<html>oops</html>")

    response = await client.get("/weather", params={"latitude": 41.7151, "longitude": 44.8271})

    assert response.status_code == 502
    assert response.json()["error"] == "upstream_bad_response"


async def test_weather_rejects_missing_current_block(
    client: httpx.AsyncClient,
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(json={"latitude": 41.7151, "longitude": 44.8271})

    response = await client.get("/weather", params={"latitude": 41.7151, "longitude": 44.8271})

    assert response.status_code == 502
    body = response.json()
    assert body["error"] == "upstream_bad_response"
    assert "current" in body["message"]


async def test_weather_rejects_missing_temperature(
    client: httpx.AsyncClient,
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(
        json={
            "latitude": 41.7151,
            "longitude": 44.8271,
            "current": {"wind_speed_10m": 12.1},
        }
    )

    response = await client.get("/weather", params={"latitude": 41.7151, "longitude": 44.8271})

    assert response.status_code == 502
    body = response.json()
    assert body["error"] == "upstream_bad_response"
    assert "temperature_2m" in body["message"]
