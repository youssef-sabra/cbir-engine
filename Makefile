.PHONY: help up down logs ps build lint format test compose-validate ci-local clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "%-18s %s\n", $$1, $$2}'

up: ## Start the full local stack (build if needed)
	docker compose up --build

down: ## Stop and remove the local stack (keeps volumes)
	docker compose down

clean: ## Stop the stack and remove volumes (destroys local data)
	docker compose down -v

logs: ## Tail logs from all services
	docker compose logs -f

ps: ## Show running services and health status
	docker compose ps

build: ## Build all Docker images without starting containers
	docker compose build

lint: ## Run formatting + lint checks (hello-world-service for now)
	cd hello-world-service && ruff format --check . && ruff check .

format: ## Auto-fix formatting and lint issues
	cd hello-world-service && ruff format . && ruff check --fix .

test: ## Run unit tests (hello-world-service for now)
	cd hello-world-service && python -m pytest -v

compose-validate: ## Validate docker-compose.yml syntax without starting anything
	docker compose config --quiet

ci-local: ## Run the same checks CI runs, locally
	$(MAKE) lint
	$(MAKE) test
	$(MAKE) build
	$(MAKE) compose-validate
	docker compose up -d
	@echo "Waiting for services to become healthy..."
	@sleep 5
	docker compose ps
	curl -sf http://localhost:8000/health || (docker compose logs && exit 1)
	curl -sf http://localhost:8000/readyz || (docker compose logs && exit 1)
	docker compose down
