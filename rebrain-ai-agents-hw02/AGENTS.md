# AGENTS.md

## Project Overview

This is a small training Python service used for coding-agent exercises.

Keep changes minimal and easy to review.

## Commands

- Install dependencies: `uv sync` or `pip install -e .`
- Run tests: `pytest`
- Run focused test: `pytest tests/test_health.py`
- Lint: `ruff check .`

## Agent Rules

- Read `README.md` before making code changes.
- Prefer focused tests before full test runs.
- Do not edit dependency files unless the task explicitly asks for it.
- Do not read or print secrets, `.env` files, tokens, credentials, or private keys.
- Before changing files, summarize the plan and expected diff.
- After changing files, show the verification command and result.
