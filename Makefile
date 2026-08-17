.PHONY: setup lint typecheck test

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
