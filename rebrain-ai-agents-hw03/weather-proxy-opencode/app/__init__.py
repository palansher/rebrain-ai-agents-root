"""Weather proxy service: FastAPI application exposing normalized Open-Meteo data."""

from app.main import app, create_app, run

__all__ = ["app", "create_app", "run"]
