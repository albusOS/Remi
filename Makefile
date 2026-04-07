.PHONY: dev dev-api dev-frontend dev-db test lint typecheck build up down logs clean

# ── Development ──────────────────────────────────────────────────────────────

dev: dev-db dev-api dev-frontend  ## Start everything for local dev

dev-db:  ## Start Postgres + Redis
	docker compose up -d postgres redis

dev-api:  ## Start the FastAPI backend (auto-reload)
	uv run remi serve --reload

dev-frontend:  ## Start the Next.js dev server
	cd frontend && npm run dev

# ── Quality ──────────────────────────────────────────────────────────────────

test:  ## Run backend tests
	uv run pytest

lint:  ## Lint backend (ruff) + frontend (eslint)
	uv run ruff check src/ tests/
	cd frontend && npm run lint

fmt:  ## Auto-format backend
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

typecheck:  ## Type-check backend (mypy) + frontend (tsc)
	uv run mypy src/
	cd frontend && npx tsc --noEmit

# ── Build ────────────────────────────────────────────────────────────────────

build:  ## Build all Docker images
	docker compose --profile prod build
	docker compose --profile build build sandbox

build-api:  ## Build API image only
	docker build -t remi-api:latest .

build-frontend:  ## Build frontend image only
	docker build -t remi-frontend:latest frontend/

build-sandbox:  ## Build sandbox image only
	docker compose --profile build build sandbox

# ── Production ───────────────────────────────────────────────────────────────

up:  ## Start full production stack
	docker compose --profile prod up -d

down:  ## Stop all services
	docker compose --profile prod down

logs:  ## Tail logs from production stack
	docker compose --profile prod logs -f

# ── Cleanup ──────────────────────────────────────────────────────────────────

clean:  ## Remove build artifacts and caches
	rm -rf .mypy_cache .pytest_cache .ruff_cache
	rm -rf frontend/.next frontend/node_modules/.cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# ── Help ─────────────────────────────────────────────────────────────────────

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
