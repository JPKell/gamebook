# Gamebook Studio — developer commands. Run `make help`.
.DEFAULT_GOAL := help
SHELL := /bin/bash

BACKEND := backend
FRONTEND := frontend

.PHONY: help install dev serve deploy install-service gen-api lint format typecheck test e2e check build clean

help: ## Show this help
	@grep -hE '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Install backend + frontend dependencies
	cd $(BACKEND) && uv sync
	cd $(FRONTEND) && npm ci

SERVICE := gamebook.service
DEV_API_PORT := 8789

dev: ## Run API (reload, :8789) and Vite (:5173) together; leaves :8788 to the service
	@trap 'kill 0' EXIT; \
	(cd $(BACKEND) && uv run gamebook serve --reload --port $(DEV_API_PORT)) & \
	(cd $(FRONTEND) && GAMEBOOK_API=http://127.0.0.1:$(DEV_API_PORT) npm run dev) & \
	wait

serve: build ## Production-style in the foreground: API serves the built UI on :8788
	cd $(BACKEND) && GAMEBOOK_FRONTEND_DIST=../$(FRONTEND)/dist uv run gamebook serve

install-service: ## Install/refresh the systemd user unit (deploy/gamebook.service)
	install -Dm644 deploy/$(SERVICE) $(HOME)/.config/systemd/user/$(SERVICE)
	systemctl --user daemon-reload
	systemctl --user enable $(SERVICE)

deploy: build ## Rebuild the UI, sync deps and restart the service on :8788
	cd $(BACKEND) && uv sync --frozen
	systemctl --user restart $(SERVICE)
	@sleep 2; curl -sf http://127.0.0.1:8788/api/health && echo

gen-api: ## Regenerate the TypeScript API types from the backend OpenAPI schema
	cd $(FRONTEND) && npm run gen:api

lint: ## Lint + format check everything
	cd $(BACKEND) && uv run ruff check . && uv run ruff format --check .
	cd $(FRONTEND) && npm run lint && npm run format:check

format: ## Auto-format everything
	cd $(BACKEND) && uv run ruff check --fix . && uv run ruff format .
	cd $(FRONTEND) && npm run format

typecheck: ## mypy + tsc
	cd $(BACKEND) && uv run mypy
	cd $(FRONTEND) && npm run typecheck

test: ## Unit/integration tests (pytest + vitest)
	cd $(BACKEND) && uv run pytest
	cd $(FRONTEND) && npm test

e2e: ## Playwright end-to-end tests (builds the UI, starts the API)
	cd $(FRONTEND) && npm run e2e

check: lint typecheck test e2e ## Everything CI runs

build: ## Build the frontend
	cd $(FRONTEND) && npm run build

clean: ## Remove build outputs and caches
	rm -rf $(FRONTEND)/dist $(FRONTEND)/.e2e-data $(FRONTEND)/test-results $(FRONTEND)/playwright-report
	find $(BACKEND) -name __pycache__ -type d -prune -exec rm -rf {} +
