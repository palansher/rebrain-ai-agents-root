"""Tests for the ``/forecast`` endpoint."""

import httpx
import pytest
from pytest_httpx import HTTPXMock


async def test_forecast_returns_normalized_days(
    client: httpx.AsyncClient,
    httpx_mock: HTTPXMock,
    forecast_payload: dict[str, object],
) -> None:
    httpx_mock.add_response(json=forecast_payload)

    response = await client.get(
        "/forecast", params={"latitude": 41.7151, "longitude": 44.8271, "days": 3}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "open-meteo"
    assert body["days"] == 3
    assert body["daily"] == [
        {
            "date": "2026-11-18",
            "weather_code": 1,
            "temp_max": 14.2,
            "temp_min": 4.1,
            "wind_speed_max": 18.5,
        },
        {
            "date": "2026-11-19",
            "weather_code": 3,
            "temp_max": 12.8,
            "temp_min": 3.4,
            "wind_speed_max": 22.0,
        },
        {
            "date": "2026-11-20",
            "weather_code": 61,
            "temp_max": 9.5,
            "temp_min": 2.0,
            "wind_speed_max": 30.7,
        },
    ]

    upstream = httpx_mock.get_requests()[0]
    assert upstream.url.params["daily"] == (
        "weather_code,temperature_2m_max,temperature_2m_min,wind_speed_10m_max"
    )
    assert upstream.url.params["forecast_days"] == "3"
    assert upstream.url.params["timezone"] == "auto"


async def test_forecast_defaults_to_three_days(
    client: httpx.AsyncClient,
    httpx_mock: HTTPXMock,
    forecast_payload: dict[str, object],
) -> None:
    httpx_mock.add_response(json=forecast_payload)

    response = await client.get("/forecast", params={"latitude": 41.7151, "longitude": 44.8271})

    assert response.status_code == 200
    assert httpx_mock.get_requests()[0].url.params["forecast_days"] == "3"


@pytest.mark.parametrize("days", [0, 8, -1])
async def test_forecast_rejects_days_out_of_range(client: httpx.AsyncClient, days: int) -> None:
    response = await client.get(
        "/forecast",
        params={"latitude": 41.7151, "longitude": 44.8271, "days": days},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "invalid_request"
    assert "days" in {detail["field"] for detail in body["details"]}


async def test_forecast_rejects_mismatched_series_lengths(
    client: httpx.AsyncClient,
    httpx_mock: HTTPXMock,
    forecast_payload: dict[str, object],
) -> None:
    daily = dict(forecast_payload["daily"])  # type: ignore[arg-type]
    daily["weather_code"] = [1, 3]
    httpx_mock.add_response(json={**forecast_payload, "daily": daily})

    response = await client.get(
        "/forecast", params={"latitude": 41.7151, "longitude": 44.8271, "days": 3}
    )

    assert response.status_code == 502
    assert response.json()["error"] == "upstream_bad_response"


async def test_forecast_rejects_invalid_date(
    client: httpx.AsyncClient,
    httpx_mock: HTTPXMock,
    forecast_payload: dict[str, object],
) -> None:
    daily = dict(forecast_payload["daily"])  # type: ignore[arg-type]
    daily["time"] = ["18.11.2026", "2026-11-19", "2026-11-20"]
    httpx_mock.add_response(json={**forecast_payload, "daily": daily})

    response = await client.get(
        "/forecast", params={"latitude": 41.7151, "longitude": 44.8271, "days": 3}
    )

    assert response.status_code == 502
    body = response.json()
    assert body["error"] == "upstream_bad_response"
    assert "date" in body["message"]
