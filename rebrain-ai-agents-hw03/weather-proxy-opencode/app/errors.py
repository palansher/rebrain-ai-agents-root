"""Domain errors and FastAPI exception handlers."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class UpstreamError(Exception):
    """Base class for every failure caused by the upstream Open-Meteo API."""

    error_code = "upstream_error"
    status_code = 502

    def __init__(self, message: str, url: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.url = url

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"error": self.error_code, "message": self.message}
        if self.url is not None:
            payload["url"] = self.url
        return payload


class UpstreamTimeoutError(UpstreamError):
    """Open-Meteo did not answer within the configured timeout."""

    error_code = "upstream_timeout"
    status_code = 504


class UpstreamUnavailableError(UpstreamError):
    """Open-Meteo could not be reached at the transport level."""

    error_code = "upstream_unavailable"
    status_code = 502


class UpstreamStatusError(UpstreamError):
    """Open-Meteo answered with a non-successful HTTP status."""

    error_code = "upstream_error"
    status_code = 502

    def __init__(
        self, message: str, url: str | None = None, upstream_status: int | None = None
    ) -> None:
        super().__init__(message, url)
        self.upstream_status = upstream_status

    def to_payload(self) -> dict[str, Any]:
        payload = super().to_payload()
        if self.upstream_status is not None:
            payload["upstream_status"] = self.upstream_status
        return payload


class UpstreamResponseError(UpstreamError):
    """Open-Meteo returned a response that cannot be normalized."""

    error_code = "upstream_bad_response"
    status_code = 502


def _validation_details(exc: RequestValidationError) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for error in exc.errors():
        location = [str(part) for part in error.get("loc", ())]
        field = ".".join(location[1:]) or ".".join(location) or "request"
        details.append(
            {
                "field": field,
                "message": error.get("msg", "Invalid value"),
                "type": error.get("type", "value_error"),
            }
        )
    return details


def register_exception_handlers(app: FastAPI) -> None:
    """Attach consistent JSON error handling to the application."""

    @app.exception_handler(UpstreamError)
    async def _handle_upstream_error(_: Request, exc: UpstreamError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": "invalid_request",
                "message": "Invalid or missing query parameters.",
                "details": _validation_details(exc),
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": "http_error", "message": str(exc.detail)},
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(_: Request, __: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": "Unexpected internal server error."},
        )
