COMPOSE_FILE := deploy/docker/docker-compose.yml
ENV_FILE := deploy/docker/.env

.PHONY: dev down logs ps seed coraza-build

dev:
	docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) up --build

down:
	docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) down -v

logs:
	docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) logs -f

ps:
	docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) ps

seed:
	docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec backend /app/.venv/bin/python scripts/seed_admin.py

coraza-build:
	docker build -f deploy/docker/coraza.Dockerfile -t guard-proxy/coraza-spoa:dev .
