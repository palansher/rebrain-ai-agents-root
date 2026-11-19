"""Запись новостей в PostgreSQL (asyncpg, идемпотентно по `link`)."""

from __future__ import annotations

import logging
from datetime import datetime

import asyncpg

logger = logging.getLogger(__name__)


async def create_pool(dsn: str) -> asyncpg.Pool:
    """Создаёт пул соединений с PostgreSQL."""
    pool = await asyncpg.create_pool(
        dsn,
        min_size=1,
        max_size=5,
        command_timeout=15,
        server_settings={"application_name": "news-worker"},
    )
    logger.info("PostgreSQL pool created")
    return pool


async def close_pool(pool: asyncpg.Pool | None) -> None:
    if pool is not None:
        await pool.close()
        logger.info("PostgreSQL pool closed")


async def upsert_news(
    pool: asyncpg.Pool, source: str, title: str, link: str, published_at: datetime, text: str
) -> int:
    """Вставляет новость или обновляет существующую по `link`.

    Повторная доставка той же ссылки не падает и не плодит дубли.
    Возвращает id существующей или только что вставленной строки.
    """
    row = await pool.fetchrow(
        """
        INSERT INTO news (source, title, link, published_at, text)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (link) DO UPDATE
            SET source    = EXCLUDED.source,
                title     = EXCLUDED.title,
                published_at = EXCLUDED.published_at,
                text      = EXCLUDED.text
        RETURNING id
        """,
        source,
        title,
        link,
        published_at,
        text,
    )
    news_id = row["id"]
    logger.info("Новость сохранена id=%s link=%s", news_id, link)
    return news_id


async def insert_entities(
    pool: asyncpg.Pool, news_id: int, entities: list[tuple[str, str, int]]
) -> int:
    """Вставить или обновить сущности новости. Идемпотентно по (news_id, text, label)."""
    if not entities:
        return 0
    inserted = 0
    async with pool.acquire() as conn, conn.transaction():
        await conn.executemany(
            """
                INSERT INTO entities (news_id, text, label, count)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (news_id, text, label) DO UPDATE
                    SET count = EXCLUDED.count
                """,
            [(news_id, text, label, count) for text, label, count in entities],
        )
        inserted = len(entities)
    logger.info("Сущности сохранены news_id=%s количество=%s", news_id, inserted)
    return inserted
