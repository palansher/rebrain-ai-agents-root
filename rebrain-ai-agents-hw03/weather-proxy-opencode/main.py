"""Entry point so that ``uv run uvicorn main:app --reload`` works from the project root."""

from app.main import app, create_app, run

__all__ = ["app", "create_app", "run"]

if __name__ == "__main__":
    run()
