# Сравнение Open-Source Coding-агентов: OpenCode, Aider и Cline

https://my.rebrainme.com/course/ai-agents-intensiv/task/5319

## API

`curl -s -S "https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&hourly=temperature_2m" | jq`

### docs

https://open-meteo.com/en/docs

## Запуск приложения с указанием локального venv окружения из текущей папки

`uv run --python .venv/bin/python uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

## Проверки

```
curl http://127.0.0.1:8000/health
# {"status":"ok"}

curl "http://127.0.0.1:8000/weather?latitude=41.7151&longitude=44.8271"
# {"latitude":41.7151,"longitude":44.8271,"temperature":...,"wind_speed":...,"source":"open-meteo"}
```

## Тестовый запрос по API документации

`uv run --no-project api_example.py`
