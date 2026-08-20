# ─────────────────────────────────────────────────────────────────────────────
# Makefile – HealthAI Platform developer shortcuts
# Usage: make <target>
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: help up down logs ps build seed test test-all lint fmt typecheck \
        migrate shell-api shell-db clean

# ─── Config ───────────────────────────────────────────────────────────────────

COMPOSE        = docker compose
PYTHON         = python3
PYTEST_FLAGS   = -v --tb=short
SHARED_PATH    = $(shell pwd)/shared

# ─── Help ─────────────────────────────────────────────────────────────────────

help:           ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Docker ───────────────────────────────────────────────────────────────────

up:             ## Start all services (detached)
	$(COMPOSE) up -d

up-build:       ## Rebuild images and start
	$(COMPOSE) up --build -d

down:           ## Stop and remove containers
	$(COMPOSE) down

down-clean:     ## Stop containers AND remove volumes
	$(COMPOSE) down -v

logs:           ## Tail logs for all services
	$(COMPOSE) logs -f --tail=50

logs-%:         ## Tail logs for a specific service (make logs-api-gateway)
	$(COMPOSE) logs -f --tail=100 $*

ps:             ## Show running containers
	$(COMPOSE) ps

build:          ## Build all Docker images
	$(COMPOSE) build

restart-%:      ## Restart one service (make restart-rag-service)
	$(COMPOSE) restart $*

# ─── Data ─────────────────────────────────────────────────────────────────────

seed:           ## Seed demo data into the running platform
	$(PYTHON) scripts/seed_demo.py

migrate:        ## Apply PostgreSQL schema migrations
	$(PYTHON) scripts/migrate_db.py

# ─── Tests ────────────────────────────────────────────────────────────────────

test:           ## Run all unit tests
	PYTHONPATH=$(SHARED_PATH) pytest $(PYTEST_FLAGS)

test-%:         ## Run tests for a specific service (make test-analytics-service)
	PYTHONPATH=$(SHARED_PATH):services/$* pytest services/$*/tests/ $(PYTEST_FLAGS)

test-cov:       ## Run all tests with HTML coverage report
	PYTHONPATH=$(SHARED_PATH) pytest $(PYTEST_FLAGS) \
	  --cov=services --cov=shared \
	  --cov-report=html:htmlcov \
	  --cov-report=term-missing
	@echo "\n📊 Coverage report: open htmlcov/index.html"

# ─── Code quality ─────────────────────────────────────────────────────────────

lint:           ## Run ruff linter
	ruff check .

fmt:            ## Auto-format with ruff
	ruff format .

fmt-check:      ## Check formatting without changing files
	ruff format --check .

typecheck:      ## Run mypy on shared/
	mypy shared/ --ignore-missing-imports

qa: fmt lint typecheck test  ## Run full quality check (fmt + lint + types + tests)

# ─── Utilities ────────────────────────────────────────────────────────────────

health:         ## Check health of all services
	@bash scripts/healthcheck.sh

shell-api:      ## Open a shell in the api-gateway container
	$(COMPOSE) exec api-gateway /bin/bash

shell-db:       ## Open psql in the postgres container
	$(COMPOSE) exec postgres psql -U postgres -d healthcare

shell-%:        ## Open a shell in any service container
	$(COMPOSE) exec $* /bin/bash

fe-dev:         ## Start frontend in dev mode (outside Docker)
	cd frontend && npm run dev

fe-install:     ## Install frontend dependencies
	cd frontend && npm ci --legacy-peer-deps

fe-build:       ## Build frontend for production
	cd frontend && npm run build

install-dev:    ## Install Python dev dependencies
	pip install \
	  pytest pytest-asyncio pytest-cov \
	  ruff mypy \
	  pydantic pydantic-settings \
	  pandas statsmodels pyyaml \
	  fastapi httpx \
	  asyncpg

load-test:      ## Run Locust load test (headless, 30s)
	pip install locust -q
	locust -f scripts/load_test.py --host http://localhost:8000 \
	  --users 20 --spawn-rate 5 --run-time 30s --headless

load-test-ui:   ## Open Locust web UI
	locust -f scripts/load_test.py --host http://localhost:8000

test-security:  ## Run security/PHI tests
	PYTHONPATH=shared pytest tests/test_security.py -v

test-integration: ## Run integration tests
	PYTHONPATH=shared:services/agent-orchestrator pytest tests/integration/ -v

migrate-local:  ## Run DB migrations against local postgres
	POSTGRES_DSN="postgresql://postgres:postgres@localhost:5432/healthcare" alembic upgrade head

create-tenant:  ## Create a tenant (make create-tenant ID=my-org NAME="My Org")
	$(PYTHON) scripts/create_tenant.py create --id $(ID) --name "$(NAME)"

list-tenants:   ## List all tenants
	$(PYTHON) scripts/create_tenant.py list

reset-demo-tenant: ## Reset the demo tenant
	$(PYTHON) scripts/create_tenant.py reset-demo

clean:          ## Remove Python cache files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -type f -name "*.pyc"     -delete 2>/dev/null; true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null; true
	find . -type d -name "htmlcov"   -exec rm -rf {} + 2>/dev/null; true
	@echo "✅  Clean complete"

# ─── Free version ─────────────────────────────────────────────────────────────

setup-free:     ## Interactive setup for the 100% free version
	bash scripts/setup_free.sh

up-free:        ## Start the free version (Groq + local embeddings)
	docker compose -f docker-compose.free.yml up -d

up-free-build:  ## Build and start the free version
	docker compose -f docker-compose.free.yml up --build -d

down-free:      ## Stop the free version
	docker compose -f docker-compose.free.yml down

logs-free:      ## Tail logs for the free version
	docker compose -f docker-compose.free.yml logs -f --tail=50

pull-ollama:    ## Pull the default Ollama model (llama3.2)
	docker compose -f docker-compose.free.yml exec ollama ollama pull llama3.2

pull-ollama-small: ## Pull tinyllama (fastest, lowest RAM: ~600MB)
	docker compose -f docker-compose.free.yml exec ollama ollama pull tinyllama
