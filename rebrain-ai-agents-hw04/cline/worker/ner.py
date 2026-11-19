"""NER-обёртка над SpaCy (ru_core_news_sm).

Модель загружается ОДИН раз при старте воркера — в глобальную переменную
``_nlp``, а не на каждое сообщение.
"""

from __future__ import annotations

import logging
from collections import Counter

import spacy

logger = logging.getLogger(__name__)

_nlp = None


def load_model(model_name: str) -> None:
    """Загрузить SpaCy-модель один раз. Повторный вызов — no-op."""
    global _nlp
    if _nlp is None:
        logger.info("Загрузка SpaCy-модели %s (один раз при старте)...", model_name)
        _nlp = spacy.load(model_name)
        logger.info("SpaCy-модель %s загружена", model_name)


def is_loaded() -> bool:
    return _nlp is not None


def extract_entities(title: str, text: str) -> list[tuple[str, str, int]]:
    """Извлечь именованные сущности из заголовка и текста.

    Возвращает список кортежей ``(entity_text, label, count)``,
    агрегированный по паре ``(text, label)`` (сколько раз сущность с таким
    текстом и такой меткой встретилась в документе).
    """
    if _nlp is None:
        raise RuntimeError("SpaCy-модель не загружена — вызовите load_model()")
    doc = _nlp(f"{title}. {text}")
    counter: Counter[tuple[str, str]] = Counter()
    for ent in doc.ents:
        entity_text = ent.text.strip()
        if entity_text:
            counter[(entity_text, ent.label_)] += 1
    return [(entity_text, label, count) for (entity_text, label), count in counter.items()]
