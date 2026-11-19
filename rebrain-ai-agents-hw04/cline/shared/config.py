from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Все параметры подключения и конфигурация системы — только из .env / env."""

    # Redis
    redis_url: str = Field(default="redis://redis:6379/0")
    redis_stream: str = Field(default="news:stream")
    redis_group: str = Field(default="news-workers")
    redis_consumer: str = Field(default="worker-1")
    redis_seen_key: str = Field(default="news:seen_links")

    # PostgreSQL
    postgres_user: str = Field(default="postgres")
    postgres_password: str = Field(default="postgres")
    postgres_db: str = Field(default="news")
    postgres_host: str = Field(default="postgres")
    postgres_port: int = Field(default=5432)

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Monitor
    poll_interval_seconds: int = Field(default=300)
    request_timeout_seconds: int = Field(default=15)
    spacy_model: str = Field(default="ru_core_news_sm")

    # RSS feeds: "Агентство" -> URL (JSON-объект в .env). Источник правды
    # для поля `source` контракта сообщения.
    rss_feeds: dict[str, str] = Field(
        default={
            "РИА Новости": "https://ria.ru/export/rss2/archive/index.xml",
            "ТАСС": "https://tass.ru/rss/v2.xml",
            "Коммерсантъ": "https://www.kommersant.ru/RSS/news.xml",
        }
    )

    # User-Agent браузера при запросе к RSS-лентам.
    rss_user_agent: str = Field(
        default="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    # Logging
    log_level: str = Field(default="INFO")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
