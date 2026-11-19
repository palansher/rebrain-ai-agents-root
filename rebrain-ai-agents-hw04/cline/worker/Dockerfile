# syntax=docker/dockerfile:1
# Stage 1: builder — ставит зависимости (здесь могут быть прокси; в рантайме их нет).
FROM python:3.12-slim AS builder

ARG UV_INDEX_URL=http://vs-nexus02.brg.loc:8081/repository/pypi-proxy/simple
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

ENV UV_INDEX_URL=${UV_INDEX_URL} \
    HTTP_PROXY=${HTTP_PROXY:-} \
    HTTPS_PROXY=${HTTPS_PROXY:-} \
    NO_PROXY=${NO_PROXY:-} \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv --seed /app/.venv \
    && . /app/.venv/bin/activate \
    && uv pip install --no-cache-dir --index-url "${UV_INDEX_URL}" \
        fastapi "uvicorn[standard]" apscheduler "faststream[redis]" \
        spacy pydantic-settings feedparser asyncpg httpx \
    && python -m spacy download ru_core_news_sm

# Stage 2: runtime — чистый образ, прокси-ENV нет физически.
FROM python:3.12-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/app/.venv/bin:$PATH

COPY --from=builder /app/.venv /app/.venv
COPY pyproject.toml uv.lock ./
COPY shared/ ./shared/
COPY worker/ ./worker/

CMD ["faststream", "run", "worker.main:app"]