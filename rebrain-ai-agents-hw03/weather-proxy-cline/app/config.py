"""Application settings loaded from environment variables and ``.env``."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Runtime configuration for the weather proxy service."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    open_meteo_base_url: str = Field(
        default="https://api.open-meteo.com",
        description="Base URL of the Open-Meteo API.",
    )
    request_timeout: float = Field(
        default=10.0,
        gt=0,
        description="Timeout in seconds for requests to Open-Meteo.",
    )
    timezone: str = Field(
        default="auto",
        description="Timezone forwarded to Open-Meteo (used by the forecast endpoint).",
    )
    host: str = Field(default="127.0.0.1", description="Host used by the ``weather-proxy`` script.")
    port: int = Field(
        default=8010, ge=1, le=65535, description="Port used by the ``weather-proxy`` script."
    )

    @field_validator("open_meteo_base_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        if not value:
            msg = "open_meteo_base_url must not be empty"
            raise ValueError(msg)
        return value


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()
