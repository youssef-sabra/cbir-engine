.PHONY: help up down logs ps build lint format test compose-validate ci-local clean \
        migrate provision db-backup db-restore

# Packages carrying their own lint/test suites. Kept as one list so adding a
# service later is a one-line change.
PY_PACKAGES = shared/domain-kernel shared/common-libs services/auth-service services/catalog-service

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

lint: ## Run formatting + lint checks across every Python package
	@for pkg in $(PY_PACKAGES); do \
		echo "== ruff: $$pkg =="; \
		(cd $$pkg && ruff format --check . && ruff check .) || exit 1; \
	done

format: ## Auto-fix formatting and lint issues across every Python package
	@for pkg in $(PY_PACKAGES); do \
		(cd $$pkg && ruff format . && ruff check --fix .); \
	done

test: ## Run unit tests across every Python package
	@for pkg in $(PY_PACKAGES); do \
		echo "== pytest: $$pkg =="; \
		(cd $$pkg && python -m pytest -q) || exit 1; \
	done

compose-validate: ## Validate docker-compose.yml syntax without starting anything
	docker compose config --quiet

migrate: ## Apply all service database migrations against the running stack
	docker compose exec auth-service alembic upgrade head
	docker compose exec catalog-service alembic upgrade head

provision: ## Create a tenant + issue an API key (usage: make provision NAME=acme)
	python scripts/provision_tenant.py --name "$(NAME)"

db-backup: ## Dump the PostgreSQL database to backups/ (see docs/RUNBOOK_BACKUP_RESTORE.md)
	./scripts/db_backup.sh

db-restore: ## Restore PostgreSQL from a dump (usage: make db-restore FILE=backups/xxx.dump)
	./scripts/db_restore.sh "$(FILE)"

ci-local: ## Run the same checks CI runs, locally
	$(MAKE) lint
	$(MAKE) test
	$(MAKE) build
	$(MAKE) compose-validate
	docker compose up -d
	@echo "Waiting for services to become healthy..."
	@sleep 10
	docker compose ps
	curl -sf http://localhost:8001/health || (docker compose logs && exit 1)
	curl -sf http://localhost:8002/health || (docker compose logs && exit 1)
	docker compose down
