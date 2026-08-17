.PHONY: setup lint typecheck test docs docs-serve

setup:
	uv sync --frozen
	uv run pre-commit install

lint:
	uv run ruff format --check .
	uv run ruff check .

typecheck:
	uv run mypy src tests

test:
	uv run pytest

docs:
	uv run mkdocs build --strict

docs-serve:
	uv run mkdocs serve
