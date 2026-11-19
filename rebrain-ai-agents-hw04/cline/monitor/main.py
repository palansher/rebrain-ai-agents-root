"""Монитор: FastAPI + APScheduler — опрос RSS-лент, публикация в Redis Stream.

Эндпоинты:
    GET  /health   -> {"status": "ok"}
    POST /refresh  -> форсирует опрос всех лент, возвращает {"new_items": N}
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from faststream.redis import RedisBroker
from redis.asyncio import Redis

from monitor.publisher import NewsPublisher
from monitor.rss import fetch_all_feeds
from shared.config import get_settings

settings = get_settings()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")

_client: httpx.AsyncClient | None = None
_redis: Redis | None = None
_broker: RedisBroker | None = None
_publisher: NewsPublisher | None = None
_poll_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _client, _redis, _broker, _publisher

    _client = httpx.AsyncClient()
    _redis = Redis.from_url(settings.redis_url)
    _broker = RedisBroker(settings.redis_url)
    try:
        await _broker.start()
    except Exception:
        logger.exception("Не удалось подключиться к Redis (%s)", settings.redis_url)
        raise
    _publisher = NewsPublisher(_redis, _broker, settings.redis_stream, settings.redis_seen_key)

    scheduler.add_job(
        run_poll,
        "interval",
        seconds=settings.poll_interval_seconds,
        max_instances=1,
        coalesce=True,
        id="poll_rss",
    )
    scheduler.start()
    logger.info(
        "Monitor started; poll interval %ss, feeds: %d",
        settings.poll_interval_seconds,
        len(settings.rss_feeds),
    )
    yield

    scheduler.shutdown(wait=False)
    if _broker:
        await _broker.stop()
    if _redis:
        await _redis.aclose()
    if _client:
        await _client.aclose()


app = FastAPI(title="News Monitor", lifespan=lifespan)


async def run_poll() -> int:
    try:
        async with _poll_lock:
            messages = await fetch_all_feeds(_client, settings.rss_feeds)
            logger.info("Опрошено лент, получено сообщений: %d", len(messages))
            new_items = await _publisher.publish(messages)
            logger.info("Опубликовано новых в очередь: %d", new_items)
            return new_items
    except Exception:
        logger.exception("Ошибка опроса RSS-лент")
        return 0


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/refresh")
async def refresh() -> dict[str, int]:
    new_items = await run_poll()
    return {"new_items": new_items}
