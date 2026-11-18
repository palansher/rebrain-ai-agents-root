"""Pydantic models describing the public API of the weather proxy."""

import datetime
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ServiceInfo(BaseModel):
    service: Literal["weather-proxy"] = "weather-proxy"
    version: str
    docs: str = Field(description="URL of the interactive API documentation.")
    endpoints: list[str] = Field(description="Available endpoint paths.")


class CurrentWeather(BaseModel):
    latitude: float = Field(description="Latitude of the returned data point.")
    longitude: float = Field(description="Longitude of the returned data point.")
    temperature: float = Field(description="Air temperature at 2 metres, degrees Celsius.")
    wind_speed: float = Field(description="Wind speed at 10 metres, km/h.")
    source: Literal["open-meteo"] = "open-meteo"


class DailyForecastItem(BaseModel):
    date: datetime.date = Field(description="Forecast day (ISO 8601).")
    weather_code: int = Field(description="WMO weather interpretation code.")
    temp_max: float = Field(description="Maximum air temperature at 2 metres, degrees Celsius.")
    temp_min: float = Field(description="Minimum air temperature at 2 metres, degrees Celsius.")
    wind_speed_max: float = Field(description="Maximum wind speed at 10 metres, km/h.")


class ForecastResponse(BaseModel):
    latitude: float
    longitude: float
    days: int = Field(description="Number of forecast days contained in the response.")
    daily: list[DailyForecastItem]
    source: Literal["open-meteo"] = "open-meteo"


class ErrorResponse(BaseModel):
    error: str = Field(description="Machine readable error code.")
    message: str = Field(description="Human readable error description.")
    url: str | None = Field(
        default=None,
        description="URL of the Open-Meteo request that caused the error, when applicable.",
    )
