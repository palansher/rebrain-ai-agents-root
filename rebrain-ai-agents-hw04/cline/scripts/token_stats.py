"""Аналитика расхода токенов по режимам Plan/Act из файла сессии Cline.

Источник данных
---------------
Cline сохраняет историю задачи в
``~/.cline/data/sessions/<sessionId>/<sessionId>.messages.json``.
У каждого ответа ассистента есть блок ``metrics``::

    {"inputTokens": 6624, "outputTokens": 118,
     "cacheReadTokens": 0, "cacheWriteTokens": 0}

и ``modelInfo``: ``{"provider": "...", "id": "..."}``.
Режим (plan/act) берётся из атрибута ``mode="plan|act"`` в теге
``<user_input mode="...">`` пользовательских сообщений.

Использование
-------------
    uv run python scripts/token_stats.py                 # последняя сессия
    uv run python scripts/token_stats.py --session PATH  # конкретная сессия
    uv run python scripts/token_stats.py --all-sessions  # все сессии суммарно
    uv run python scripts/token_stats.py --json          # вывод в JSON
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

SESSIONS_DIR = Path.home() / ".cline" / "data" / "sessions"
_MODE_RE = re.compile(r'mode="(plan|act)"')


@dataclass
class Bucket:
    """Суммарные метрики по одной паре (режим, модель)."""

    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read: int = 0
    cache_write: int = 0

    def add_metrics(self, metrics: dict) -> None:
        self.requests += 1
        self.input_tokens += int(metrics.get("inputTokens") or 0)
        self.output_tokens += int(metrics.get("outputTokens") or 0)
        self.cache_read += int(metrics.get("cacheReadTokens") or 0)
        self.cache_write += int(metrics.get("cacheWriteTokens") or 0)

    def merge(self, other: Bucket) -> None:
        self.requests += other.requests
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read += other.cache_read
        self.cache_write += other.cache_write

    @property
    def uncached_input(self) -> int:
        """Input-токены, не покрытые кэшем (тарифицируются по полной)."""
        return self.input_tokens - self.cache_read

    @property
    def cache_pct(self) -> float:
        return 100.0 * self.cache_read / self.input_tokens if self.input_tokens else 0.0

    def avg(self, value: int) -> float:
        return value / self.requests if self.requests else 0.0

    def as_dict(self, mode: str, provider: str, model: str) -> dict:
        return {
            "mode": mode,
            "provider": provider,
            "model": model,
            "requests": self.requests,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read": self.cache_read,
            "cache_write": self.cache_write,
            "uncached_input": self.uncached_input,
            "cache_pct": round(self.cache_pct, 1),
            "avg_input": round(self.avg(self.input_tokens), 1),
            "avg_output": round(self.avg(self.output_tokens), 1),
            "avg_uncached": round(self.avg(self.uncached_input), 1),
        }


def session_files() -> list[Path]:
    """Все файлы сессий Cline, отсортированные по времени изменения."""
    if not SESSIONS_DIR.is_dir():
        return []
    return sorted(
        SESSIONS_DIR.glob("*/*.messages.json"),
        key=lambda path: path.stat().st_mtime,
    )


def message_text(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, list):
        return " ".join(part.get("text", "") for part in content if isinstance(part, dict))
    return str(content or "")


def collect(path: Path, mode: str, buckets: dict[tuple[str, str, str], Bucket]) -> str:
    """Наполнить buckets данными из файла сессии; вернуть актуальный режим."""
    data = json.loads(path.read_text(encoding="utf-8"))
    for message in data.get("messages", []):
        role = message.get("role")
        if role == "user":
            found = _MODE_RE.search(message_text(message))
            if found:
                mode = found.group(1)
            continue
        metrics = message.get("metrics")
        if role != "assistant" or not metrics:
            continue
        info = message.get("modelInfo") or {}
        key = (mode, info.get("provider") or "?", info.get("id") or "?")
        buckets.setdefault(key, Bucket()).add_metrics(metrics)
    return mode


def merge_by_mode(buckets: dict[tuple[str, str, str], Bucket]) -> dict[str, Bucket]:
    result: dict[str, Bucket] = {}
    for (mode, _provider, _model), bucket in buckets.items():
        result.setdefault(mode, Bucket()).merge(bucket)
    return result


HEADER = [
    "mode",
    "model",
    "req",
    "input",
    "avg_in",
    "output",
    "avg_out",
    "cache_read",
    "cache%",
    "uncached_in",
    "avg_unc",
]


def _table(rows: list[list[str]]) -> str:
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    lines = []
    for row in rows:
        cells = [
            cell.ljust(widths[index]) if index < 2 else cell.rjust(widths[index])
            for index, cell in enumerate(row)
        ]
        lines.append("  ".join(cells).rstrip())
    return "\n".join(lines)


def _row(mode: str, model: str, bucket: Bucket) -> list[str]:
    return [
        mode,
        model,
        f"{bucket.requests:,d}",
        f"{bucket.input_tokens:,d}",
        f"{bucket.avg(bucket.input_tokens):,.0f}",
        f"{bucket.output_tokens:,d}",
        f"{bucket.avg(bucket.output_tokens):,.0f}",
        f"{bucket.cache_read:,d}",
        f"{bucket.cache_pct:.1f}%",
        f"{bucket.uncached_input:,d}",
        f"{bucket.avg(bucket.uncached_input):,.0f}",
    ]


def render(buckets: dict[tuple[str, str, str], Bucket]) -> str:
    by_mode = merge_by_mode(buckets)
    mode_rows = [HEADER]
    for mode, bucket in sorted(by_mode.items()):
        mode_rows.append(_row(mode, "все модели", bucket))

    total = Bucket()
    for bucket in by_mode.values():
        total.merge(bucket)
    mode_rows.append(_row("TOTAL", "все режимы", total))

    detail_rows = [HEADER]
    for (mode, provider, model), bucket in sorted(
        buckets.items(), key=lambda item: (item[0][0], -item[1].requests)
    ):
        detail_rows.append(_row(mode, f"{provider}/{model}", bucket))

    return (
        "=== ПО РЕЖИМАМ ===\n"
        + _table(mode_rows)
        + "\n\n=== ПО РЕЖИМ x МОДЕЛЬ ===\n"
        + _table(detail_rows)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Статистика токенов Cline по режимам Plan/Act")
    parser.add_argument("--session", type=Path, help="путь к <id>.messages.json")
    parser.add_argument("--all-sessions", action="store_true", help="суммировать все сессии")
    parser.add_argument("--json", action="store_true", help="вывод в JSON")
    args = parser.parse_args()

    if args.session:
        files = [args.session]
    elif args.all_sessions:
        files = session_files()
    else:
        files = session_files()[-1:]
    if not files:
        print(f"Файлы сессий не найдены: {SESSIONS_DIR}")
        return 1

    buckets: dict[tuple[str, str, str], Bucket] = {}
    mode = "unknown"
    for path in files:
        mode = collect(path, mode, buckets)

    if args.json:
        payload = [
            bucket.as_dict(mode_, provider, model)
            for (mode_, provider, model), bucket in sorted(buckets.items())
        ]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print("Источник:")
    for path in files:
        print(f"  {path}")
    print()
    print(render(buckets))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
