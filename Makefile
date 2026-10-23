# Run `make` with no target to list commands.
.PHONY: list setup check fmt test test-all db db-stop migrate serve image up down

list:
	@awk -F':.*# ' '/^[a-z-]+:.*# /{printf "  %-10s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: # install dependencies into .venv
	uv sync

check: # lint, format check, and lockfile check
	uv lock --check
	uv run ruff check .
	uv run ruff format --check .

fmt: # auto-fix lint and formatting
	uv run ruff check --fix .
	uv run ruff format .

test: # unit tests, no database or API key needed
	uv run pytest -m "not db" --cov

test-all: # all tests; needs `make db` first
	TEST_DATABASE_URL=postgresql://hpc:hpc@localhost:5432/hpc_rag_test uv run pytest --cov

db: # start Postgres+pgvector in Docker
	docker compose up -d --wait db

db-stop: # stop the database container
	docker compose stop db

migrate: # apply database migrations
	uv run slu-hpc-rag-migrate

serve: # run the API with auto-reload on :8000
	uv run uvicorn slu_hpc_rag.main:app --reload

image: # build the Docker image
	docker compose build app

up: # run database + API in Docker
	docker compose up -d --build

down: # stop everything
	docker compose down
