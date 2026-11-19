# Инструкции и шаги для тебя (копировать в Cline по очереди)

После каждого шага делай **checkpoint** (в Cline кнопка Checkpoint либо `git add -A && git commit -m "step N"`). В Plan mode агент не трогает файлы; переключайся в Act mode только когда план шага согласован.

## Подготовительный промпт (отправь перед Шагом 1)

Прочитай `.clinerules` и `TASK.md` целиком.
Работаем только в `/home/vp/my/rebrain/rebrain-ai-agents/rebrain-ai-agents-hw04/cline`.
Подтверди, что понял правила, архитектуру и контракт сообщения. Пока не пиши код — жди шаг 1.

## Шаг 1. Скелет проекта + docker-compose (Plan mode)

```markdown
Шаг 1:

создание скелета проекта 
и 
`docker-compose.yml` (redis, postgres, monitor, worker),
`init.sql` со схемой `news` и `entities`, `.env` + `.env.example`,
`pyproject.toml` (добавить зависимости: fastapi, uvicorn, apscheduler, faststream[redis], spacy, pydantic-settings, feedparser, asyncpg, httpx),
`shared/config.py`,`shared/schemas.py` с моделью `NewsMessage`,
пустые `monitor/Dockerfile`, `worker/Dockerfile`.

Убедись, что `.env` НЕ в `.gitignore`, а `.venv/` — в `.gitignore`.
В Dockerfile используй официальный образ uv (например, `COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/`).

Не пиши код, пока не покажешь план. Затем переключись в Act mode и реализуй.
```

*Проверка после шага:*

```bash
uv sync
uv run ruff format . && uv run ruff check .
docker-compose config
```

## Шаг 2. Monitor: парсинг RSS + дедупликация + публикация (Plan mode)

Шаг 2:
реализовать
`monitor/main.py` (FastAPI + APScheduler с интервалом 5 минут),
`monitor/rss.py` (парсинг минимум 3 лент через feedparser, передача User-Agent браузера при запросе, обработка ошибок недоступной ленты),
`monitor/publisher.py` (публикация в Redis Stream, дедупликация по `link` — используй Redis SET или поле в БД).

Эндпоинты: `GET /health`, `POST /refresh`. `/refresh` возвращает `{"new_items": N}`.
Покажи план, потом Act mode.

*Проверка:*

```bash
docker-compose up --build redis postgres monitor
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/refresh
```

## Шаг 3. Worker: FastStream subscriber + запись news в БД (Plan mode)

Шаг 3:
реализовать
`worker/main.py` (FastStream подписчик на Redis Stream, consumer group),
`worker/db.py` (asyncpg, UPSERT в `news` по `link`, чтобы повторная доставка не падала).

NER пока не подключать — только запись новости.
Покажи план, потом Act mode.

*Проверка:*

```bash
docker-compose up --build
curl -X POST http://127.0.0.1:8000/refresh
docker-compose exec postgres psql -U postgres -d news -c "SELECT id, source, title FROM news LIMIT 5;"
```

## Шаг 4. Worker: SpaCy NER + запись entities (Plan mode)

Шаг 4:
реализовать
`worker/ner.py` — загрузка `ru_core_news_sm` ОДИН раз при старте (глобальная переменная/синглтон), функция извлечения сущностей из `title + text`, подсчёт `count` по (text, label).
Обновить `worker/main.py` — после записи news вызвать NER и вставить entities.

Добавить `uv add spacy` и инструкцию установки модели `ru_core_news_sm` в Dockerfile воркера (`RUN uv run python -m spacy download ru_core_news_sm`).

Обработка ошибок NER на одном сообщении — лог + continue.

Покажи план, потом Act mode.

*Проверка:*

```bash
docker-compose up --build
curl -X POST http://127.0.0.1:8000/refresh
docker-compose exec postgres psql -U postgres -d news -c "SELECT n.source, n.title, e.label, e.text FROM news n JOIN entities e ON e.news_id = n.id ORDER BY n.created_at DESC LIMIT 20;"
```

## Шаг 5. Обработка ошибок, ruff, README (Plan mode)

Шаг 5:

### a)

пройтись по всем сервисам и убедиться, что ошибки ловятся и логируются (недоступная лента, битый XML, падение NER на одном сообщении, ошибка БД);

### b)

прогнать `uv run ruff format . && uv run ruff check . --fix`, исправить всё;

### c)

написать `README.md` по структуре:

- архитектура (с ASCII-схемой)
- выбор брокера (1-2 строки обоснования)
- инструкция запуска
- команды проверки
- раздел «Наблюдения по применению Plan/Act и architect/editor» (оставь заготовку с подзаголовками, заполним вручную позже).

Покажи план, потом Act mode.

## Шаг 6. Финальный прогон по чек-листу (Act mode)

Шаг 6:

Пройди по чек-листу из `TASK.md` («Критерии готовности») и отметь каждый пункт.
Запусти `docker-compose down -v && docker-compose up --build`, выполни 4 команды проверки из раздела «Как проверить результат» и покажи вывод.
Если что-то не работает — исправь и повтори.
