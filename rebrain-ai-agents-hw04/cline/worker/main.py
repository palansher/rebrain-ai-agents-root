"""Воркер с NER: FastStream подписчик на Redis Stream, запись в Postgres.

Контракт сообщения (из shared.schemas.NewsMessage):
    source, title, link, published_at, text

Хендлер обязательно на FastStream (@broker.subscriber), читает из Redis Stream
через consumer group. Ошибка на одном сообщении не роняет сервис: логировать и
продолжать. NER-модель SpaCy ru_core_news_sm загружается один раз при старте.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from faststream import AckPolicy, FastStream
from faststream.redis import RedisBroker, StreamSub

from shared.config import get_settings
from shared.schemas import NewsMessage
from worker.db import close_pool, create_pool, insert_entities, upsert_news
from worker.ner import extract_entities, is_loaded, load_model

settings = get_settings()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)
broker = RedisBroker(settings.redis_url)
_pool = None


@asynccontextmanager
async def lifespan():
    global _pool
    _pool = await create_pool(settings.postgres_dsn)
    try:
        load_model(settings.spacy_model)
    except Exception:
        logger.exception(
            "Критическая ошибка: не удалось загрузить SpaCy-модель %s", settings.spacy_model
        )
        raise
    logger.info(
        "Worker started; stream=%s, group=%s, model=%s",
        settings.redis_stream,
        settings.redis_group,
        settings.spacy_model,
    )
    yield
    await close_pool(_pool)
    _pool = None


app = FastStream(broker, lifespan=lifespan)


@broker.subscriber(
    stream=StreamSub(
        settings.redis_stream,
        group=settings.redis_group,
        consumer=settings.redis_consumer,
        declare=True,
    ),
    ack_policy=AckPolicy.REJECT_ON_ERROR,
)
async def handle_news(message: NewsMessage) -> None:
    """Обработать одно сообщение из очереди: записать в Postgres + NER.

    Любая ошибка логируется и перехватывается — сервис не падает.
    """
    if _pool is None:
        logger.error("PostgreSQL pool is not ready; skipping %s", message.link)
        return

    try:
        news_id = await upsert_news(
            _pool,
            source=message.source,
            title=message.title,
            link=message.link,
            published_at=message.published_at,
            text=message.text,
        )
    except Exception:
        logger.exception("Не удалось сохранить новость %s", message.link)
        return

    if not is_loaded():
        logger.error("NER-модель не загружена; пропуск entidades для %s", message.link)
        return

    try:
        entities = extract_entities(message.title, message.text)
        await insert_entities(_pool, news_id, entities)
    except Exception:
        logger.exception("NER не справился с новостью %s", message.link)
