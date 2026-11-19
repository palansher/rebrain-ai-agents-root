from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NewsMessage(BaseModel):
    """Контракт сообщения в Redis Stream (Monitor -> Worker)."""

    source: str = Field(min_length=1, description="Название агентства (пример: РИА Новости)")
    title: str = Field(min_length=1, description="Заголовок новости")
    link: str = Field(min_length=1, description="Уникальная ссылка — ключ дедупликации")
    published_at: datetime = Field(description="Дата публикации, ISO-8601 / tz-aware UTC")
    text: str = Field(default="", description="Описание или полный текст новости")

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")
