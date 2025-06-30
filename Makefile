# Makefile for Video Creation API
# Usage: make <target>

.PHONY: help setup build up down logs clean dev prod test

# Default target
help:
	@echo "Video Creation API - Docker Management"
	@echo ""
	@echo "Available targets:"
	@echo "  setup     - Create necessary directories and .env file"
	@echo "  build     - Build Docker images"
	@echo "  up        - Start development environment"
	@echo "  down      - Stop all services"
	@echo "  logs      - Show logs"
	@echo "  clean     - Clean up containers, volumes, and images"
	@echo "  dev       - Start development environment with hot reload"
	@echo "  prod      - Start production environment"
	@echo "  test      - Run tests in container"
	@echo "  shell     - Open shell in running container"
	@echo "  health    - Check service health"

# Setup directories and environment
setup:
	@echo "Setting up environment..."
	@if [ -f setup-directories.sh ]; then chmod +x setup-directories.sh && ./setup-directories.sh; else cmd //c setup-directories.bat; fi
	@if [ ! -f .env ]; then cp .env.template .env && echo "Created .env file from template. Please edit it."; fi

# Build images
build:
	docker-compose build --no-cache

# Start development environment
up: setup
	docker-compose up -d

# Stop all services
down:
	docker-compose down

# Show logs
logs:
	docker-compose logs -f

# Clean up everything
clean:
	docker-compose down -v --remove-orphans
	docker system prune -f
	docker volume prune -f

# Development environment with hot reload
dev: setup
	docker-compose -f docker-compose.yml -f docker-compose.override.yml up

# Production environment
prod: setup
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Production deployment with domain setup
deploy-prod:
	@echo "🚀 Production deployment..."
	@if [ -f deploy-production.sh ]; then chmod +x deploy-production.sh && ./deploy-production.sh; else cmd //c deploy-production.bat; fi

# Production with custom environment file
prod-env:
	@if [ ! -f .env.prod ]; then echo "❌ .env.prod not found. Run 'make deploy-prod' first"; exit 1; fi
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod up -d

# Run tests
test:
	docker-compose exec video python -m pytest test/ -v

# Open shell in container
shell:
	docker-compose exec video /bin/bash

# Check health
health:
	@echo "Checking service health..."
	@curl -f http://localhost:8000/health || echo "Service is not healthy"

# Restart service
restart:
	docker-compose restart video

# View resource usage
stats:
	docker stats cont_video cont_ngrok

# Backup volumes
backup:
	@echo "Backing up data volumes..."
	@mkdir -p backups
	@docker run --rm -v video-create_video_logs:/data -v $(PWD)/backups:/backup alpine tar czf /backup/logs-$(shell date +%Y%m%d_%H%M%S).tar.gz -C /data .
	@echo "Backup completed in backups/ directory"

# Show container information
info:
	@echo "=== Container Status ==="
	@docker-compose ps
	@echo ""
	@echo "=== Resource Usage ==="
	@docker stats --no-stream cont_video cont_ngrok 2>/dev/null || echo "Containers not running"
	@echo ""
	@echo "=== Volume Information ==="
	@docker volume ls | grep video-create
