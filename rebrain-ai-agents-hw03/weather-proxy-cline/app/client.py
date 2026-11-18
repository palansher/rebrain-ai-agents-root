"""Async client for the Open-Meteo API with response normalization."""

from datetime import date
from typing import Any

import httpx

from app.config import Settings
from app.errors import (
    UpstreamResponseError,
    UpstreamStatusError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)
from app.schemas import CurrentWeather, DailyForecastItem, ForecastResponse

FORECAST_PATH = "/v1/forecast"
CURRENT_FIELDS = "temperature_2m,wind_speed_10m"
DAILY_FIELDS = "weather_code,temperature_2m_max,temperature_2m_min,wind_speed_10m_max"


def _request_url(exc: Exception, http: httpx.AsyncClient, path: str) -> str:
    request = getattr(exc, "request", None)
    if request is not None:
        return str(request.url)
    base = str(getattr(http, "base_url", "")).rstrip("/")
    return f"{base}{path}"


def _as_float(value: Any, name: str, url: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise UpstreamResponseError(f"Unexpected value for '{name}': {value!r}", url=url)
    return float(value)


def _as_int(value: Any, name: str, url: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise UpstreamResponseError(f"Unexpected value for '{name}': {value!r}", url=url)
    return int(value)


def _section(payload: dict[str, Any], name: str, url: str) -> dict[str, Any]:
    value = payload.get(name)
    if not isinstance(value, dict):
        raise UpstreamResponseError(f"Open-Meteo response is missing the '{name}' object", url=url)
    return value


def _series(section: dict[str, Any], name: str, url: str) -> list[Any]:
    value = section.get(name)
    if not isinstance(value, list) or not value:
        raise UpstreamResponseError(f"Open-Meteo response is missing the '{name}' series", url=url)
    return value


class OpenMeteoClient:
    """Thin wrapper around ``httpx.AsyncClient`` returning normalized models."""

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        self._http = http
        self._settings = settings

    async def _get_json(
        self, path: str, params: dict[str, str | int | float]
    ) -> tuple[dict[str, Any], str]:
        try:
            response = await self._http.get(path, params=params)
        except httpx.TimeoutException as exc:
            raise UpstreamTimeoutError(
                f"Open-Meteo did not respond within {self._settings.request_timeout:g} seconds",
                url=_request_url(exc, self._http, path),
            ) from exc
        except httpx.HTTPError as exc:
            raise UpstreamUnavailableError(
                f"Failed to reach Open-Meteo: {exc.__class__.__name__}: {exc}",
                url=_request_url(exc, self._http, path),
            ) from exc

        url = str(response.request.url)
        if response.status_code != httpx.codes.OK:
            raise UpstreamStatusError(
                f"Open-Meteo responded with HTTP {response.status_code}",
                url=url,
                upstream_status=response.status_code,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise UpstreamResponseError("Open-Meteo returned a non-JSON response", url=url) from exc
        if not isinstance(payload, dict):
            raise UpstreamResponseError("Open-Meteo returned an unexpected JSON structure", url=url)
        return payload, url

    async def get_current(self, latitude: float, longitude: float) -> CurrentWeather:
        """Fetch current conditions for a single point."""
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": CURRENT_FIELDS,
        }
        payload, url = await self._get_json(FORECAST_PATH, params)
        current = _section(payload, "current", url)

        return CurrentWeather(
            latitude=_as_float(payload.get("latitude", latitude), "latitude", url),
            longitude=_as_float(payload.get("longitude", longitude), "longitude", url),
            temperature=_as_float(current.get("temperature_2m"), "current.temperature_2m", url),
            wind_speed=_as_float(current.get("wind_speed_10m"), "current.wind_speed_10m", url),
        )

    async def get_forecast(self, latitude: float, longitude: float, days: int) -> ForecastResponse:
        """Fetch a daily forecast for a single point."""
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": DAILY_FIELDS,
            "forecast_days": days,
            "timezone": self._settings.timezone,
        }
        payload, url = await self._get_json(FORECAST_PATH, params)
        daily = _section(payload, "daily", url)

        raw_dates = _series(daily, "time", url)
        raw_codes = _series(daily, "weather_code", url)
        raw_max = _series(daily, "temperature_2m_max", url)
        raw_min = _series(daily, "temperature_2m_min", url)
        raw_wind = _series(daily, "wind_speed_10m_max", url)

        lengths = {
            len(raw_dates),
            len(raw_codes),
            len(raw_max),
            len(raw_min),
            len(raw_wind),
        }
        if len(lengths) != 1:
            raise UpstreamResponseError(
                "Open-Meteo returned daily series of different lengths", url=url
            )

        items: list[DailyForecastItem] = []
        for index, raw_date in enumerate(raw_dates):
            try:
                parsed_date = date.fromisoformat(str(raw_date))
            except ValueError as exc:
                raise UpstreamResponseError(
                    f"Unexpected date in Open-Meteo response: {raw_date!r}", url=url
                ) from exc
            items.append(
                DailyForecastItem(
                    date=parsed_date,
                    weather_code=_as_int(raw_codes[index], "daily.weather_code", url),
                    temp_max=_as_float(raw_max[index], "daily.temperature_2m_max", url),
                    temp_min=_as_float(raw_min[index], "daily.temperature_2m_min", url),
                    wind_speed_max=_as_float(raw_wind[index], "daily.wind_speed_10m_max", url),
                )
            )

        return ForecastResponse(
            latitude=_as_float(payload.get("latitude", latitude), "latitude", url),
            longitude=_as_float(payload.get("longitude", longitude), "longitude", url),
            days=len(items),
            daily=items,
        )
