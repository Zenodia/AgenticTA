.PHONY: help up down restart build gradio test clean status logs shell

# Default target
help:
	@echo "╔═══════════════════════════════════════════════════════════╗"
	@echo "║          AgenticTA - Development Commands                ║"
	@echo "╚═══════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "  make up          - Start all services (use existing images)"
	@echo "  make down        - Stop all services"
	@echo "  make restart     - Restart all services"
	@echo "  make build       - Build ta_master image only"
	@echo "  make rebuild     - Rebuild ALL images and restart"
	@echo "  make gradio      - Start Gradio UI"
	@echo "  make test        - Test LLM module"
	@echo "  make status      - Show service status"
	@echo "  make logs        - View container logs"
	@echo "  make shell       - Enter container shell"
	@echo "  make clean       - Remove all containers and volumes"
	@echo ""
	@echo "Quick Start:"
	@echo "  1. make up        # Start everything (fast, uses existing images)"
	@echo "  2. make gradio    # Start Gradio UI"
	@echo "  3. open http://localhost:7860"
	@echo ""
	@echo "To rebuild after Dockerfile changes:"
	@echo "  make build        # Rebuild only ta_master (faster)"
	@echo "  make rebuild      # Rebuild everything (slower, avoid if possible)"
	@echo ""

# Start all services with Docker Compose (uses existing images)
up:
	@echo "Starting all services with Docker Compose..."
	@docker compose up -d
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

# Stop all services
down:
	@echo "Stopping all services..."
	@docker compose down
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
	@docker compose exec -d agenticta bash -c "cd /workspace && python gradioUI.py > /tmp/gradio.log 2>&1"
	@sleep 3
	@echo "✅ Gradio UI started"
	@echo "  → http://localhost:7860"
	@echo "  View logs: make logs-gradio"

# Stop Gradio UI
stop-gradio:
	@docker compose exec agenticta pkill -f gradioUI.py || echo "Gradio not running"
	@echo "✅ Gradio stopped"

# Restart Gradio UI
restart-gradio: stop-gradio
	@sleep 1
	@make gradio

# Test LLM module
test:
	@echo "Testing LLM module..."
	@docker compose exec agenticta python -c "from llm import LLMClient; from llm.config import load_config; print('✅ LLM module OK'); c=load_config(); print(f'✅ Config: {len(c[\"providers\"])} providers, {len(c[\"use_cases\"])} use cases')"

# Show service status
status:
	@echo "╔═══════════════════════════════════════════════════════════╗"
	@echo "║                   Service Status                          ║"
	@echo "╚═══════════════════════════════════════════════════════════╝"
	@docker compose ps

# Show logs
logs:
	@docker compose logs -f agenticta

logs-gradio:
	@docker compose exec agenticta tail -f /tmp/gradio.log

logs-rag:
	@docker compose logs -f rag-server

logs-all:
	@docker compose logs -f

# Enter container shell
shell:
	@docker compose exec agenticta /bin/bash

# Clean everything (containers, volumes, images)
clean:
	@echo "Cleaning up everything..."
	@docker compose down -v --remove-orphans
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
	@docker compose exec agenticta pip install -q aiohttp pyyaml
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
	@docker compose exec milvus curl -s http://localhost:9091/healthz | head -c 100 || echo "  ❌ Not responding"
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
