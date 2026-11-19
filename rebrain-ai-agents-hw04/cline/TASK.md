# TASK: Event-driven система мониторинга новостей с NER

Полное техническое задание. Читать целиком перед началом работы.
При сомнениях в требовании — сверяться с этим файлом, не додумывать.

## Цель

Собрать event-driven систему мониторинга новостей из RSS-лент нескольких
российских информационных агентств. Система полностью локальная, без
платных внешних API. Стек: Python 3.12, UV, ruff, FastStream, SpaCy,
Redis, PostgreSQL, Docker Compose.

## Архитектура (утверждена)

```
RSS-ленты (РИА, ТАСС, Коммерсантъ)
        │
        ▼
Monitor (FastAPI + APScheduler)
  - раз в 5 минут опрашивает ленты
  - POST /refresh — форс-опрос вне расписания
  - дедупликация по link
        │ publish
        ▼
Queue: Redis Streams (redis:7-alpine)
        │ consume (FastStream)
        ▼
Worker (FastStream + SpaCy ru_core_news_sm)
  - NER: PER, ORG, LOC
  - запись в Postgres
        │
        ▼
PostgreSQL (postgres:16-alpine)
```

### Обоснование выбора (для README)

- **Планировщик:** APScheduler (AsyncIOScheduler) внутри процесса монитора —
  не нужен отдельный cron-контейнер, не блокирует HTTP, легко форсировать
  через /refresh.
- **Брокер:** Redis Streams — лёгкий образ, персистентность и consumer groups
  (в отличие от Pub/Sub), нативная поддержка в FastStream. Для локального
  учебного проекта проще RabbitMQ.
- **Схема БД:** SQL-скрипт `init.sql` через `docker-entrypoint-initdb.d` —
  схема фиксирована (2 таблицы), Alembic избыточен.

## 1. Monitor (контейнер мониторинга)

Отдельный сервис/контейнер, который:

- раз в 5 минут опрашивает RSS-ленты минимум 3 российских агентств;
- парсит новые записи (заголовок, ссылка, дата публикации, описание/текст);
- дедуплицирует записи по `link` (повторный опрос не плодит дубли). Redis SET (`SADD`, ключ из `.env`). Это нужно, чтобы `new_items` в `/refresh` оставался честным после рестарта контейнера и не зависел от БД. Монитор не должен напрямую ходить в Postgres. Логика проверки перед публикацией в очередь: `SADD` возвращает 1, если ссылки не было, и 0, если она уже есть — публикуем только если 1. ;
- публикует новые сообщения в Redis Stream;
- поднимает HTTP-эндпоинты:
  - `GET /health` → `{"status": "ok"}`
  - `POST /refresh` → запускает внеочередной опрос всех лент,
    возвращает счётчик новых новостей: `{"new_items": N}`

Примеры RSS-лент (минимум 3):

- РИА Новости — https://ria.ru/export/rss2/archive/index.xml
- ТАСС — https://tass.ru/rss/v2.xml
- Коммерсантъ — https://www.kommersant.ru/RSS/news.xml
Если лента недоступна — заменить на рабочую и зафиксировать в README.

## 2. Queue (брокер)

- Redis Streams, поднимается в docker-compose.yml.
- Монитор публикует, воркер читает через consumer group.
- Сообщение содержит: source, title, link, published_at, text.

## 3. Worker (воркер с NER)

- Хендлер ОБЯЗАТЕЛЬНО на FastStream (`@broker.subscriber`).
- На каждое сообщение — NER моделью SpaCy `ru_core_news_sm`.
- Извлекает сущности (PER, ORG, LOC и т.п.) из заголовка и текста.
- Записывает результат в PostgreSQL.
- Модель загружается ОДИН раз при старте, не на каждое сообщение.
- Ошибка на одном сообщении не роняет сервис: логировать и продолжать.

## 4. PostgreSQL (хранилище)

Минимальная схема:

- таблица `news`: id, source, title, link (UNIQUE), published_at, text, created_at
- таблица `entities`: id, news_id (FK -> news.id), text, label, count

## Правила проекта

- Python 3.12, пакетный менеджер — UV.
- ruff format + ruff check после каждого изменения, все замечания исправлять.
- Хендлер воркера — на FastStream.
- NER — SpaCy с русскоязычной моделью.
- Очередь и Postgres — только через docker-compose.
- Секреты и параметры подключения — из .env/settings, не хардкодить.
- `.env` НЕ в .gitignore (секретов нет, нужен для проверки преподавателем).

## Критерии готовности

- [ ] `docker-compose up --build` поднимает всю систему: redis, postgres, monitor, worker.
- [ ] Monitor раз в 5 минут опрашивает минимум 3 RSS-ленты и публикует новые новости в очередь.
- [ ] Работает `POST /refresh` — форсирует опрос и возвращает число новых новостей.
- [ ] Дедупликация: повторный опрос не плодит дубли одной новости.
- [ ] Хендлер воркера реализован на FastStream и читает из очереди.
- [ ] Воркер выполняет NER моделью SpaCy и извлекает именованные сущности.
- [ ] Результат (новости + сущности) записывается в PostgreSQL по схеме.
- [ ] Конфигурация подключений вынесена в .env/settings.
- [ ] `ruff format` и `ruff check` проходят без замечаний.
- [ ] README.md: архитектура, выбор брокера, инструкция запуска.
- [ ] README.md: наблюдения по применению architect/editor и/или Plan/Act.

## Как проверить результат

```bash
# 1. Поднять всю систему
docker-compose up --build

# 2. Проверить, что монитор жив
curl http://127.0.0.1:8000/health
# → {"status": "ok"}

# 3. Форсировать опрос лент
curl -X POST http://127.0.0.1:8000/refresh
# → {"new_items": N}

# 4. Убедиться, что воркер обработал сообщения и записал сущности в БД

docker-compose exec postgres psql -U postgres -d news -c \
"SELECT n.source, n.title, e.label, e.text FROM news n JOIN entities e ON e.news_id = n.id ORDER BY n.created_at DESC LIMIT 20;"
```

Признак успеха: после /refresh в таблице news появляются свежие новости из
разных агентств, а в entities — извлечённые SpaCy сущности (персоны,
организации, локации), связанные с новостями.
