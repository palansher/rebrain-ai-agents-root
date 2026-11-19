# Расположение весов SpaCy-модели `ru_core_news_sm`

Документ описывает, где физически хранятся веса языковой модели, как они попадают
в Docker-образ и почему системе не нужен интернет при работе.

Версии: `spacy==3.8.18`, модель `ru_core_news_sm==3.8.0`,
словари `pymorphy3-dicts-ru==2.4.417150.4580142`.

## Кратко

SpaCy-модель в этой конфигурации — **обычный Python-пакет внутри venv**, а не
отдельный каталог с кэшем. Никаких загрузок при старте контейнера не происходит:
веса лежат в образе и читаются с диска.

## 1. В worker-контейнере (используется в работе)

```
/app/.venv/lib/python3.12/site-packages/ru_core_news_sm/       ← 45 MB
└── ru_core_news_sm-3.8.0/
    ├── config.cfg, meta.json, accuracy.json, LICENSE, README.md
    ├── vocab/           32 MB    — лексикон и векторные представления
    ├── tok2vec/          6.0 MB  — эмбеддинги токенов
    ├── ner/              5.9 MB  — веса NER (дают PER / ORG / LOC)
    ├── morphologizer/    488 KB
    ├── parser/           320 KB
    ├── senter/           204 KB
    ├── lemmatizer/        12 KB
    └── attribute_ruler/    8 KB
```

Зависимость модели — русские морфологические словари:

```
/app/.venv/lib/python3.12/site-packages/pymorphy3_dicts_ru/    ← 16 MB
```

## 2. Локально в проекте (только для проверок до сборки образа)

```
.venv/lib/python3.12/site-packages/ru_core_news_sm/            ← 45 MB
```

- в git не попадает: `.venv/` указан в `.gitignore`;
- в Docker-контекст не попадает: `.venv/` указан в `.dockerignore`.

## 3. Как модель попадает в образ

`worker/Dockerfile`:

1. **builder-стадия**: `uv venv --seed /app/.venv` (флаг `--seed` ставит `pip`,
   без него `spacy download` не работает) → `uv pip install …` →
   `python -m spacy download ru_core_news_sm`.
   Команда `spacy download` — это установка wheel-файла модели
   (`ru_core_news_sm-3.8.0-py3-none-any.whl`, ~15 MB) с GitHub releases
   `explosion/spacy-models` в текущее окружение.
2. **runtime-стадия**: `COPY --from=builder /app/.venv /app/.venv` — веса
   переносятся в финальный образ слоем вместе с остальными зависимостями.

## 4. Проверки (фактические, на запущенном контейнере)

| Утверждение | Как проверено | Результат |
|---|---|---|
| Модель лежит в venv | `import ru_core_news_sm; dirname(__file__)` | `/app/.venv/lib/python3.12/site-packages/ru_core_news_sm` |
| Размер модели | `du -sh` | 45 MB |
| Размер словарей | `du -sh pymorphy3_dicts_ru` | 16 MB |
| Кэшей в рантайме нет | `ls /root/.cache`, `ls /root/.local/share` | пусто |
| Загрузка без сети | логи воркера при старте | «Загрузка SpaCy-модели…» → «загружена» (~1.9 с) |
| Симлинков `spacy/data` нет | `ls site-packages/spacy/data` | каталога нет (механика spaCy 2.x) |

`spacy.load("ru_core_news_sm")` в spaCy 3.x находит модель через entry point
установленного пакета (`importlib.metadata`), поэтому отдельный каталог кэша
не нужен.

## 5. Что это даёт

- **Офлайн-совместимость:** образ самодостаточен, при работе система не обращается
  к GitHub/PyPI и не зависит от прокси.
- **Предсказуемый старт:** модель загружается один раз при старте воркера (~2 с)
  и переиспользуется для всех сообщений.
- **Воспроизводимость:** версия модели зафиксирована в `uv.lock`, а wheel
  скачивается на этапе сборки, а не в рантайме.

## 6. Если понадобится уменьшить образ

Веса (45 MB) + словари (16 MB) + сам `spacy` — заметная часть образа. Варианты:

- вынести модель в отдельный named volume и ставить при первом старте — но тогда
  появляется сетевая зависимость при инициализации;
- собирать образ без модели и монтировать каталог с весами read-only.

Для текущего задания офлайн-образ удобнее: `docker compose up --build` поднимает
систему без внешних обращений к модели.

## 7. Как проверить у себя

```bash
# путь и размер модели внутри контейнера
docker compose exec -T worker python -c "
import os, ru_core_news_sm
p = os.path.dirname(ru_core_news_sm.__file__)
print(p, '%.1f MB' % (sum(os.path.getsize(os.path.join(r, f))
      for r, _, fs in os.walk(p) for f in fs) / 1024 / 1024))
"

# размеры компонентов модели
docker compose exec -T worker sh -c \
  'cd /app/.venv/lib/python3.12/site-packages/ru_core_news_sm/ru_core_news_sm-3.8.0 && du -sh */ | sort -h'
```