# InterCraft dev Makefile
# Phase 1: no Docker, no Postgres in repo. Use T008b to plug DATABASE_URL.

.PHONY: up down test e2e seed reset gen-api lint typecheck backend-test backend-migrate

up:
	bash scripts/dev-up.sh

down:
	@echo "Nothing to bring down (no docker compose). Stop uvicorn/vite with Ctrl-C."

backend-test:
	cd backend && uv run pytest -q

backend-migrate:
	cd backend && uv run alembic upgrade head

seed:
	cd backend && uv run python -m app.cli.main seed

reset:
	cd backend && uv run python -m app.cli.main reset-db --yes

gen-api:
	npm run gen:api

test:
	npm test

e2e:
	npx playwright test

lint:
	npm run lint

typecheck:
	npm run typecheck
