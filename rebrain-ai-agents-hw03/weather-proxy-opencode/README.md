# Weather Proxy Service

FastAPI-прокси над [Open-Meteo API](https://open-meteo.com/en/docs): принимает координаты,
запрашивает данные у Open-Meteo через `httpx.AsyncClient` и возвращает нормализованный JSON
с понятными ошибками.

## Возможности

- `GET /` — краткая информация о сервисе и список эндпоинтов.
- `GET /health` — проверка живости сервиса.
- `GET /weather` — текущая температура (`temperature_2m`) и скорость ветра (`wind_speed_10m`).
- `GET /forecast` — прогноз на 1–7 дней: `weather_code`, `temperature_2m_max`,
  `temperature_2m_min`, `wind_speed_10m_max` (в ответе — `wind_speed_max`).
- Валидация параметров (`latitude` −90…90, `longitude` −180…180, `days` 1…7).
- Единый формат ошибок с указанием проблемного URL Open-Meteo.
- Таймауты и недоступность upstream, невалидный JSON и неожиданная структура ответа
  обрабатываются отдельными `502`/`504`-ответами.

## Требования

- Python 3.12 (`~=3.12.0`)
- [uv](https://docs.astral.sh/uv/)

## Установка

```bash
git clone <repository-url> weather-proxy-opencode
cd weather-proxy-opencode
uv sync
```

`uv sync` создаст локальное окружение `.venv` и установит все зависимости
(включая dev-группу: `ruff`, `pytest`, `pytest-httpx`).

## Конфигурация

Скопируйте пример окружения и при необходимости измените значения:

```bash
cp .env.example .env
```

| Переменная             | По умолчанию                | Назначение                                              |
| ---------------------- | --------------------------- | ------------------------------------------------------- |
| `OPEN_METEO_BASE_URL`  | `https://api.open-meteo.com` | Базовый URL Open-Meteo (без завершающего `/`)           |
| `REQUEST_TIMEOUT`      | `10`                        | Таймаут запроса к Open-Meteo в секундах                 |
| `TIMEZONE`             | `auto`                      | Таймзона, передаваемая в `/forecast`                    |
| `HOST`                 | `127.0.0.1`                 | Хост для `uv run weather-proxy`                          |
| `PORT`                 | `8010`                      | Порт для `uv run weather-proxy`                          |

Файл `.env` в git не попадает (см. `.gitignore`), в репозитории хранится только `.env.example`.
Путь к `.env` определяется относительно корня проекта, поэтому настройки подхватываются
независимо от текущей рабочей директории. Переменные окружения процесса имеют приоритет
над значениями из `.env`.

## Запуск

Два поддерживаемых способа:

```bash
# 1) uvicorn из корня проекта (с авто-перезагрузкой)
uv run uvicorn main:app --reload

# 2) консольный скрипт из [project.scripts]
uv run weather-proxy
```

Сервис будет доступен по адресу <http://127.0.0.1:8010>, интерактивная документация —
<http://127.0.0.1:8010/docs>.

## Примеры запросов

### Информация о сервисе

```bash
curl -s http://127.0.0.1:8010/
# {"service":"weather-proxy","version":"0.1.0","docs":"/docs",
#  "endpoints":["/health","/weather","/forecast","/docs","/openapi.json"]}
```

### Health

```bash
curl -s http://127.0.0.1:8010/health
# {"status":"ok"}
```

### Текущая погода

```bash
curl -s "http://127.0.0.1:8010/weather?latitude=41.7151&longitude=44.8271" | jq
```

```json
{
  "latitude": 41.7151,
  "longitude": 44.8271,
  "temperature": 28.4,
  "wind_speed": 12.1,
  "source": "open-meteo"
}
```

### Прогноз на 3 дня

```bash
curl -s "http://127.0.0.1:8010/forecast?latitude=41.7151&longitude=44.8271&days=3" | jq
```

```json
{
  "latitude": 41.7151,
  "longitude": 44.8271,
  "days": 3,
  "daily": [
    {
      "date": "2026-11-18",
      "weather_code": 1,
      "temp_max": 14.2,
      "temp_min": 4.1,
      "wind_speed_max": 18.5
    }
  ],
  "source": "open-meteo"
}
```

### Ошибки

Невалидные параметры:

```bash
curl -s -i "http://127.0.0.1:8010/weather?latitude=100&longitude=44.8271"
# HTTP/1.1 422 Unprocessable Entity
# {"error":"invalid_request","message":"Invalid or missing query parameters.",
#  "details":[{"field":"latitude","message":"Input should be less than or equal to 90","type":"less_than_equal"}]}
```

Таймаут upstream:

```bash
# REQUEST_TIMEOUT=0.001 в .env
curl -s -i "http://127.0.0.1:8010/weather?latitude=41.7151&longitude=44.8271"
# HTTP/1.1 504 Gateway Timeout
# {"error":"upstream_timeout","message":"Open-Meteo did not respond within 0.001 seconds",
#  "url":"https://api.open-meteo.com/v1/forecast?latitude=41.7151&..."}
```

Коды ошибок:

| Код | `error`                 | Причина                                                  |
| --- | ----------------------- | -------------------------------------------------------- |
| 422 | `invalid_request`       | Невалидные или отсутствующие query-параметры             |
| 502 | `upstream_unavailable`  | Не удалось установить соединение с Open-Meteo            |
| 502 | `upstream_error`        | Open-Meteo ответил статусом, отличным от `200`           |
| 502 | `upstream_bad_response` | Не-JSON ответ или неожиданная структура данных           |
| 504 | `upstream_timeout`      | Open-Meteo не ответил за `REQUEST_TIMEOUT` секунд         |
| 500 | `internal_error`        | Непредвиденная внутренняя ошибка                         |

## Тесты

```bash
uv run pytest
```

Тесты используют `pytest-httpx` и не обращаются к реальному Open-Meteo: проверяются
успешные сценарии, валидация входных данных, таймауты, ошибки соединения, не-`200`
ответы и некорректные структуры данных.

## Линтер и форматтер

```bash
uv run ruff format
uv run ruff check --fix
```

## Структура проекта

```text
.
├── main.py              # шим для `uvicorn main:app`
├── app/
│   ├── api.py           # роутеры /health, /weather, /forecast
│   ├── client.py        # httpx-клиент Open-Meteo и нормализация ответов
│   ├── config.py        # настройки из .env (pydantic-settings)
│   ├── errors.py        # доменные ошибки и exception handlers
│   ├── main.py          # create_app(), lifespan, точка входа weather-proxy
│   └── schemas.py       # Pydantic-модели ответов и ошибок
└── tests/               # pytest + pytest-httpx
```
