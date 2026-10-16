.PHONY: setup lint test run clean

setup:
	uv sync --all-groups

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check --fix .

test:
	uv run pytest

run:
	uv run python -m efuel_ci.pipeline

clean:
	rm -rf results/*.json results/*.csv .pytest_cache .ruff_cache
