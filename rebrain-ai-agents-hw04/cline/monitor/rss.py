"""Парсинг RSS-лент (feedparser) и загрузка через httpx.

Все функции чистые/тестируемые без сети: ``parse_feed`` принимает уже
скачанные байты, сетевой слой выделен в ``fetch_feed`` / ``fetch_all_feeds``.
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
from datetime import UTC, datetime

import feedparser
from pydantic import ValidationError

from shared.config import get_settings
from shared.schemas import NewsMessage

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _clean_html(raw: str | None) -> str:
    """Убирает HTML-теги, сущности и сжимает пробелы."""
    if not raw:
        return ""
    text = _TAG_RE.sub(" ", raw)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def _parse_published(entry: dict) -> datetime:
    """Берёт дату публикации из entry; всегда возвращает tz-aware UTC."""
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        return datetime(*parsed[:6], tzinfo=UTC)
    return datetime.now(UTC)


def parse_feed(source: str, raw: bytes) -> list[NewsMessage]:
    """Парсит фид из сырых байтов; не ходит в сеть."""
    parsed = feedparser.parse(raw)
    if parsed.bozo:
        logger.warning(
            "Повреждённый XML в ленте %s: %s", source, getattr(parsed, "bozo_exception", None)
        )
    if not parsed.entries:
        logger.warning("Лента %s не содержит записей", source)
    messages: list[NewsMessage] = []
    for entry in parsed.entries or []:
        link = (entry.get("link") or entry.get("id") or "").strip()
        title = (entry.get("title") or "").strip()
        if not link or not title:
            continue
        text = _clean_html(entry.get("summary") or entry.get("description"))
        if not text:
            text = title  # РИА не присылает summary — используем заголовок
        try:
            messages.append(
                NewsMessage(
                    source=source,
                    title=title,
                    link=link,
                    published_at=_parse_published(entry),
                    text=text,
                )
            )
        except ValidationError:
            logger.warning("Пропущена некорректная запись ленты %s (link=%s)", source, link)
            continue
    return messages


async def fetch_feed(client, source: str, url: str) -> list[NewsMessage]:
    """Скачивает фид и парсит его. Любая ошибка -> пустой список + warning."""
    settings = get_settings()
    try:
        response = await client.get(
            url,
            headers={"User-Agent": settings.rss_user_agent},
            timeout=settings.request_timeout_seconds,
            follow_redirects=True,
        )
        response.raise_for_status()
    except Exception:
        logger.exception("Не удалось скачать RSS-ленту %s (%s)", source, url)
        return []
    try:
        return await asyncio.to_thread(parse_feed, source, response.content)
    except Exception:
        logger.exception("Не удалось распарсить RSS-ленту %s (%s)", source, url)
        return []


async def fetch_all_feeds(client, feeds: dict[str, str]) -> list[NewsMessage]:
    """Опрашивает все ленты параллельно."""
    results = await asyncio.gather(
        *[fetch_feed(client, source, url) for source, url in feeds.items()],
        return_exceptions=True,
    )
    messages: list[NewsMessage] = []
    for result in results:
        if isinstance(result, Exception):
            logger.exception("Unexpected error fetching feed: %r", result)
            continue
        messages.extend(result)
    return messages
