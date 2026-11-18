"""HTTP routes of the weather proxy service."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.client import OpenMeteoClient
from app.schemas import CurrentWeather, ErrorResponse, ForecastResponse, HealthResponse, ServiceInfo

router = APIRouter()

VERSION = "0.1.0"

Latitude = Annotated[
    float,
    Query(ge=-90, le=90, description="Latitude in decimal degrees."),
]
Longitude = Annotated[
    float,
    Query(ge=-180, le=180, description="Longitude in decimal degrees."),
]
Days = Annotated[
    int,
    Query(ge=1, le=7, description="Number of forecast days (1-7)."),
]

UPSTREAM_RESPONSES: dict[int | str, dict[str, object]] = {
    502: {"model": ErrorResponse, "description": "Open-Meteo is unreachable or returned bad data."},
    504: {"model": ErrorResponse, "description": "Open-Meteo request timed out."},
}


def get_open_meteo(request: Request) -> OpenMeteoClient:
    """Return the shared Open-Meteo client created during application startup."""
    return request.app.state.open_meteo


OpenMeteoDep = Annotated[OpenMeteoClient, Depends(get_open_meteo)]


@router.get("/", response_model=ServiceInfo, summary="Service information")
async def root() -> ServiceInfo:
    return ServiceInfo(
        version=VERSION,
        docs="/docs",
        endpoints=["/health", "/weather", "/forecast", "/docs", "/openapi.json"],
    )


@router.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/health", response_model=HealthResponse, summary="Service health check")
async def health() -> HealthResponse:
    return HealthResponse()


@router.get(
    "/weather",
    response_model=CurrentWeather,
    summary="Current weather for a point",
    responses=UPSTREAM_RESPONSES,
)
async def weather(
    client: OpenMeteoDep,
    latitude: Latitude,
    longitude: Longitude,
) -> CurrentWeather:
    return await client.get_current(latitude, longitude)


@router.get(
    "/forecast",
    response_model=ForecastResponse,
    summary="Daily forecast for a point",
    responses=UPSTREAM_RESPONSES,
)
async def forecast(
    client: OpenMeteoDep,
    latitude: Latitude,
    longitude: Longitude,
    days: Days = 3,
) -> ForecastResponse:
    return await client.get_forecast(latitude, longitude, days)
