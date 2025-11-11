.PHONY: help setup up down restart build gradio test test-cov test-llm clean status logs shell test-container

# Docker Compose file configuration for older Docker Compose versions (< v2.20)
# Uses multiple -f flags instead of 'include' directive
COMPOSE_FILES := -f docker-compose.yml \
	-f ./rag/deploy/compose/vectordb.yaml \
	-f ./rag/deploy/compose/docker-compose-ingestor-server.yaml \
	-f ./rag/deploy/compose/docker-compose-rag-server.yaml
COMPOSE_ENV := --env-file ./rag/deploy/compose/.env

# Override PROMPT_CONFIG_FILE to use correct absolute path from AgenticTA directory
export PROMPT_CONFIG_FILE := $(CURDIR)/rag/src/nvidia_rag/rag_server/prompt.yaml

# Default target
help:
	@echo "╔═══════════════════════════════════════════════════════════╗"
	@echo "║          AgenticTA - Development Commands                ║"
	@echo "╚═══════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "  make setup            - Create required directories (run once)"
	@echo "  make up               - Start all services (without Vault)"
	@echo "  make up-with-vault    - Start all services WITH local vault"
	@echo "  make down             - Stop all services"
	@echo "  make restart          - Restart all services"
	@echo "  make build            - Build ta_master image only"
	@echo "  make rebuild          - Rebuild ALL images and restart"
	@echo "  make gradio           - Start Gradio UI"
	@echo ""
	@echo "Testing:"
	@echo "  make test             - Run UNIT tests only (fast, ~5s)"
	@echo "  make test-all         - Run ALL tests including integration (~17s)"
	@echo "  make test-cov         - Run tests with coverage report"
	@echo "  make test-llm         - Quick LLM module check"
	@echo "  make test-container   - Run agenticta container standalone (no deps)"
	@echo ""
	@echo "Monitoring:"
	@echo "  make status      - Show service status"
	@echo "  make logs        - View container logs"
	@echo "  make shell       - Enter container shell"
	@echo "  make clean       - Remove all containers and volumes"
	@echo ""
	@echo "Vault (optional - for secrets management):"
	@echo "  make up-with-vault   - Start services WITH Vault enabled"
	@echo "  make vault-check     - Check if Vault is running and has secrets"
	@echo "  make vault-migrate   - Migrate secrets from .env to Vault"
	@echo "  Note: Vault is OPTIONAL. 'make up' uses .env files instead."
	@echo ""
	@echo "Quick Start:"
	@echo "  1. make setup     # Create required directories (first time only)"
	@echo "  2. make up        # Start everything (fast, uses existing images)"
	@echo "  3. make gradio    # Start Gradio UI"
	@echo "  4. open http://localhost:7860"
	@echo ""
	@echo "To rebuild after Dockerfile changes:"
	@echo "  make build        # Rebuild only ta_master (faster)"
	@echo "  make rebuild      # Rebuild everything (slower, avoid if possible)"
	@echo ""

# Setup required directories for Docker volumes
setup:
	@echo "Creating required directories for Docker volumes..."
	@mkdir -p rag/deploy/compose/volumes/{milvus,etcd,minio,elasticsearch,ingestor-server}
	@echo "✅ Directories created successfully!"
	@echo "Note: If you get permission errors, run:"
	@echo "  sudo mkdir -p rag/deploy/compose/volumes/{milvus,etcd,minio,elasticsearch,ingestor-server}"
	@echo "  sudo chown -R $$USER:$$USER rag/deploy/compose/volumes/"

# Start all services with Docker Compose (uses existing images)
up:
	@echo "Starting all services with Docker Compose..."
	@echo ""
	@echo "⚠️  NOTE: Running without Vault (using environment variables from .env)"
	@echo "   To use Vault for secrets management, run: make up-with-vault"
	@echo ""
	@docker compose $(COMPOSE_FILES) $(COMPOSE_ENV) up -d
	@echo ""
	@echo "✅ All services started!"
	@echo ""
	@echo "  • Gradio UI: Run 'make gradio' then visit http://localhost:7860"
	@echo "  • RAG Server:    http://localhost:8081"
	@echo "  • RAG Frontend:  http://localhost:8090"
	@echo "  • Milvus:        http://localhost:19530"
	@echo ""
	@echo "  View status: make status"
	@echo "  View logs:   make logs"
	@echo ""
	@echo "💡 Tip: Use 'make rebuild' to rebuild images"

# Start with local vault-dev (development)
up-with-vault:
	@echo "Starting all services WITH local vault-dev..."
	@docker compose $(COMPOSE_FILES) -f docker-compose.vault-local.yml $(COMPOSE_ENV) up -d
	@echo ""
	@echo "✅ All services started (with Vault)!"
	@echo ""
	@echo "⏳ Waiting for Vault to be ready..."
	@sleep 5
	@echo ""
	@echo "📋 Next steps:"
	@echo "  1. Migrate secrets: make vault-migrate"
	@echo "  2. Check secrets:   make vault-check"
	@echo "  3. Start Gradio:    make gradio"
	@echo ""
	@echo "💡 Vault UI: http://localhost:8200 (token: dev-root-token-agenticta)"

# Stop all services
down:
	@echo "Stopping all services..."
	@docker compose $(COMPOSE_FILES) $(COMPOSE_ENV) down
	@if docker ps -a --filter "name=agenticta-vault-dev" --format "{{.Names}}" | grep -q "agenticta-vault-dev" 2>/dev/null; then \
		echo "Stopping vault-dev..."; \
		docker stop agenticta-vault-dev 2>/dev/null || true; \
		docker rm agenticta-vault-dev 2>/dev/null || true; \
		docker network rm agenticta-vault-network 2>/dev/null || true; \
	fi
	@echo "✅ All services stopped"

# Restart all services
restart: down up
	@echo "✅ All services restarted!"

# Build Docker image only (without starting)
build:
	@echo "Building ta_master image..."
	@docker build -t ta_master:latest .
	@echo "✅ Image built successfully"

# Start Gradio UI in the container
gradio:
	@echo "Starting Gradio UI..."
	@docker compose $(COMPOSE_FILES) $(COMPOSE_ENV) exec -d agenticta bash -c "cd /workspace && python gradioUI.py > /tmp/gradio.log 2>&1"
	@sleep 3
	@echo "✅ Gradio UI started"
	@echo "  → http://localhost:7860"
	@echo "  View logs: make logs-gradio"

# Stop Gradio UI
stop-gradio:
	@docker compose $(COMPOSE_FILES) $(COMPOSE_ENV) exec agenticta pkill -f gradioUI.py || echo "Gradio not running"
	@echo "✅ Gradio stopped"

# Restart Gradio UI
restart-gradio: stop-gradio
	@sleep 1
	@make gradio

# Run test suite
test:
	@echo "Running unit tests (fast)..."
	@echo "Tip: Use 'make test-all' to include integration tests"
	@docker compose $(COMPOSE_FILES) $(COMPOSE_ENV) exec agenticta pytest -v -m "not integration and not slow"

test-all:
	@echo "Running ALL tests (unit + integration + slow)..."
	@docker compose $(COMPOSE_FILES) $(COMPOSE_ENV) exec agenticta pytest -v

# Run tests with coverage
test-cov:
	@echo "Running tests with coverage..."
	@echo "Note: Coverage data will be stored in /tmp to avoid permission issues"
	@docker compose $(COMPOSE_FILES) $(COMPOSE_ENV) exec -e COVERAGE_FILE=/tmp/.coverage agenticta pytest --cov=. --cov-report=term-missing --cov-report=html
	@echo "✅ Coverage report generated: htmlcov/index.html"

# Quick LLM module check
test-llm:
	@echo "Testing LLM module..."
	@docker compose $(COMPOSE_FILES) $(COMPOSE_ENV) exec agenticta python -c "from llm import LLMClient; from llm.config import load_config; print('✅ LLM module OK'); c=load_config(); print(f'✅ Config: {len(c[\"providers\"])} providers, {len(c[\"use_cases\"])} use cases')"

# Show service status
status:
	@echo "╔═══════════════════════════════════════════════════════════╗"
	@echo "║                   Service Status                          ║"
	@echo "╚═══════════════════════════════════════════════════════════╝"
	@docker compose $(COMPOSE_FILES) $(COMPOSE_ENV) ps

# Show logs
logs:
	@docker compose $(COMPOSE_FILES) $(COMPOSE_ENV) logs -f agenticta

logs-gradio:
	@docker compose $(COMPOSE_FILES) $(COMPOSE_ENV) exec agenticta tail -f /tmp/gradio.log

logs-rag:
	@docker compose $(COMPOSE_FILES) $(COMPOSE_ENV) logs -f rag-server

logs-all:
	@docker compose $(COMPOSE_FILES) $(COMPOSE_ENV) logs -f

# Enter container shell
shell:
	@docker compose $(COMPOSE_FILES) $(COMPOSE_ENV) exec agenticta /bin/bash

# Run agenticta container alone (for testing)
test-container:
	@echo "Starting agenticta container standalone (no dependencies)..."
	@docker run -it --rm \
		-e NVIDIA_API_KEY="${NVIDIA_API_KEY}" \
		-e ASTRA_TOKEN="${ASTRA_TOKEN}" \
		-e HF_TOKEN="${HF_TOKEN}" \
		-v $(CURDIR):/workspace \
		-w /workspace \
		-p 7860:7860 \
		ta_master:latest \
		/bin/bash
	@echo "Container exited"

# Clean everything (containers, volumes, images)
clean:
	@echo "Cleaning up everything..."
	@docker compose $(COMPOSE_FILES) $(COMPOSE_ENV) down -v --remove-orphans
	@docker system prune -f
	@echo "✅ Cleanup complete"

# Full rebuild from scratch
rebuild: clean
	@docker build --no-cache -t ta_master:latest .
	@make up
	@echo "✅ Full rebuild complete!"

# Install dependencies in running container
install-deps:
	@echo "Installing Python dependencies..."
	@docker compose $(COMPOSE_FILES) $(COMPOSE_ENV) exec agenticta pip install -q aiohttp pyyaml
	@echo "✅ Dependencies installed"

# Quick development workflow
dev: up
	@echo ""
	@echo "╔═══════════════════════════════════════════════════════════╗"
	@echo "║         Development Environment Ready!                    ║"
	@echo "╚═══════════════════════════════════════════════════════════╝"
	@echo ""
	@make status
	@echo ""
	@echo "Next: make gradio"
	@echo ""

# Health check all services
health:
	@echo "Checking service health..."
	@echo ""
	@echo "RAG Server:"
	@curl -s http://localhost:8081/v1/health | head -c 100 || echo "  ❌ Not responding"
	@echo ""
	@echo "Ingestor:"
	@curl -s http://localhost:8082/v1/health | head -c 100 || echo "  ❌ Not responding"
	@echo ""
	@echo "Milvus:"
	@docker compose $(COMPOSE_FILES) $(COMPOSE_ENV) exec milvus curl -s http://localhost:9091/healthz | head -c 100 || echo "  ❌ Not responding"
	@echo ""

# Show helpful information
info:
	@echo "╔═══════════════════════════════════════════════════════════╗"
	@echo "║                  AgenticTA Information                    ║"
	@echo "╚═══════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Service URLs:"
	@echo "  • Gradio UI:     http://localhost:7860"
	@echo "  • RAG Server:    http://localhost:8081"
	@echo "  • RAG Frontend:  http://localhost:8090"
	@echo "  • Ingestor:      http://localhost:8082"
	@echo "  • Milvus:        http://localhost:19530"
	@echo ""
	@echo "Container Name: agenticta"
	@echo "Docker Compose Version:"
	@docker compose version
	@echo ""
	@echo "Configuration Files:"
	@echo "  • docker-compose.yml  - Service orchestration"
	@echo "  • llm_config.yaml     - LLM configuration"
	@echo "  • requirements.txt    - Python dependencies"
	@echo ""
	@echo "Vault (optional dev/testing):"
	@echo "  make vault-dev-start  - Start local Vault (then run: source .env.vault-local)"
	@echo "  make vault-dev-stop   - Stop local Vault"
	@echo "  make vault-check      - Check what secrets are in Vault"
	@echo ""
	@echo "  ⚠️  After vault-dev-start, run: source .env.vault-local"
	@echo "  See scripts/vault/    - For production Vault setup"
	@echo ""

# ============================================================================
# Vault Integration (Optional - for testing Vault integration locally)
# ============================================================================
# Note: Local Vault is for DEVELOPMENT/TESTING only, not for production!
# Production uses NVIDIA's Vault with OIDC authentication.
# See scripts/vault/README.md for details.

.PHONY: vault-dev-start vault-dev-stop vault-check vault-migrate

vault-dev-start:
	@echo "Starting local Vault (development only)..."
	@./scripts/vault/start_local_vault.sh

vault-dev-stop:
	@echo "Stopping local Vault..."
	@./scripts/vault/stop_local_vault.sh

vault-check:
	@echo "Checking Vault secrets..."
	@echo ""
	@if ! docker ps --filter "name=agenticta" --format "{{.Names}}" | grep -q "agenticta"; then \
		echo "⚠️  AgenticTA container not running. Start with: make up-with-vault"; \
		exit 1; \
	fi
	@if ! docker ps --filter "name=vault-dev" --format "{{.Names}}" | grep -q "vault"; then \
		echo "⚠️  Vault is not running!"; \
		echo ""; \
		echo "This is EXPECTED if you started with 'make up' (Vault is optional)."; \
		echo ""; \
		echo "To use Vault:"; \
		echo "  1. Stop services:       make down"; \
		echo "  2. Start with Vault:    make up-with-vault"; \
		echo "  3. Migrate secrets:     make vault-migrate"; \
		echo "  4. Check again:         make vault-check"; \
		echo ""; \
		exit 1; \
	fi
	@docker compose $(COMPOSE_FILES) $(COMPOSE_ENV) exec -e VAULT_ADDR=http://vault-dev:8200 -e VAULT_TOKEN=dev-root-token-agenticta agenticta python scripts/vault/list_secrets.py || \
		(echo ""; \
		 echo "⚠️  Could not connect to Vault or retrieve secrets."; \
		 echo "   Make sure you ran 'make up-with-vault' and 'make vault-migrate'."; \
		 exit 1)

vault-migrate:
	@echo "Migrating secrets from .env to Vault..."
	@if docker ps --filter "name=agenticta" --format "{{.Names}}" | grep -q "agenticta"; then \
		docker compose $(COMPOSE_FILES) $(COMPOSE_ENV) exec -e VAULT_ADDR=http://vault-dev:8200 -e VAULT_TOKEN=dev-root-token-agenticta agenticta python scripts/vault/migrate_secrets_to_vault.py; \
	else \
		echo "⚠️  AgenticTA container not running. Start with: make up"; \
		exit 1; \
	fi

# Production deployment with Vault
.PHONY: deploy-prod
deploy-prod:
	@echo "Deploying with production Vault..."
	@if [ -z "$$VAULT_TOKEN" ]; then \
		echo "❌ VAULT_TOKEN not set. Get token with:"; \
		echo "   ./scripts/vault/get_vault_token.sh"; \
		echo "   Or set manually: export VAULT_TOKEN=your-token"; \
		exit 1; \
	fi
	@echo "✅ VAULT_TOKEN found"
	@docker compose $(COMPOSE_FILES) -f docker-compose.vault-prod.yml $(COMPOSE_ENV) up -d
	@echo "✅ Deployed with production Vault"
