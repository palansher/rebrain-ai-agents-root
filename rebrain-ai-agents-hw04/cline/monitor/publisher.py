"""Публикация сообщений в Redis Stream с дедупликацией по ``link`` (Redis SET).

Публикуем только если ``SADD(seen_key, link)`` вернул 1 (ссылки ещё не было).
При ошибке публикации делаем ``SREM`` (откат дедупа), чтобы новость не
пропала навсегда, и продолжаем дальше.
"""

from __future__ import annotations

import logging

from redis.asyncio import Redis

from shared.schemas import NewsMessage

logger = logging.getLogger(__name__)


class NewsPublisher:
    def __init__(
        self,
        redis: Redis,
        broker,
        stream: str,
        seen_key: str,
    ) -> None:
        self._redis = redis
        self._broker = broker
        self._stream = stream
        self._seen_key = seen_key

    async def publish(self, messages: list[NewsMessage]) -> int:
        """Опубликовать новые сообщения; вернуть число опубликованных."""
        published = 0
        for msg in messages:
            try:
                added = await self._redis.sadd(self._seen_key, msg.link)
            except Exception:
                # Redis недоступен — дальше пытаться бессмысленно,
                # ленты будут переопрошены на следующем цикле.
                logger.exception(
                    "Redis недоступен, публикация прервана (опубликовано %d из %d)",
                    published,
                    len(messages),
                )
                break

            if added != 1:
                logger.debug("Пропуск дубликата %s", msg.link)
                continue

            try:
                await self._broker.publish(
                    msg.model_dump(mode="json"),
                    stream=self._stream,
                )
                published += 1
            except Exception:
                # Откатываем дедуп, чтобы новость не потерялась навсегда.
                try:
                    await self._redis.srem(self._seen_key, msg.link)
                except Exception:
                    logger.exception("Не удалось откатить дедуп для %s", msg.link)
                logger.exception("Не удалось опубликовать сообщение %s", msg.link)
        return published
