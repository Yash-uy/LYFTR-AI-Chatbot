.PHONY: up down logs test
up:
	@if [ ! -f .env ]; then cp .env.example .env; echo 'Created .env from .env.example. Add two real API keys, then run make up again.'; exit 1; fi
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

test:
	cd backend && python -m pytest -q
