.PHONY: up up-fast up-d down logs ps rebuild dev dev-backend dev-frontend dev-backend-fast dev-frontend-fast dev-parallel dev-clean dev-quick dev-fast dev-quick-fast

PY := $(shell if [ -x "$(CURDIR)/.venv/bin/python" ]; then printf '%s' "$(CURDIR)/.venv/bin/python"; else command -v python3 >/dev/null 2>&1 && command -v python3 || command -v python >/dev/null 2>&1 && command -v python || printf 'python'; fi)

up:
	docker compose up --build

up-fast:
	docker compose up

up-d:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

ps:
	docker compose ps

rebuild:
	docker compose build --no-cache

dev:
	@echo "Run in two terminals:"
	@echo "1) make dev-backend"
	@echo "2) make dev-frontend"
	@echo ""
	@echo "Or run both in parallel:"
	@echo "make dev-parallel"
	@echo ""
	@echo "Or clean locks + run both:"
	@echo "make dev-quick"
	@echo ""
	@echo "Fast (skip installs):"
	@echo "make dev-fast"
	@echo ""
	@echo "Fast + clean:"
	@echo "make dev-quick-fast"

dev-backend:
	cd backend && "$(PY)" -m pip install -r requirements.txt && "$(PY)" -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

dev-frontend:
	cd frontend && npm install && NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8001 npm run dev

dev-parallel:
	$(MAKE) -j2 dev-backend dev-frontend

dev-backend-fast:
	cd backend && "$(PY)" -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

dev-frontend-fast:
	cd frontend && NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8001 npm run dev

dev-clean:
	@lsof -nP -iTCP:3000 | awk 'NR>1 {print $$2}' | xargs -r kill || true
	@lsof -nP -iTCP:8001 | awk 'NR>1 {print $$2}' | xargs -r kill || true
	@rm -f "frontend/.next/dev/lock"

dev-quick: dev-clean
	$(MAKE) -j2 dev-backend dev-frontend

dev-fast:
	$(MAKE) -j2 dev-backend-fast dev-frontend-fast

dev-quick-fast: dev-clean
	$(MAKE) -j2 dev-backend-fast dev-frontend-fast
