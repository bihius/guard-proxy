COMPOSE_FILE := deploy/docker/docker-compose.yml
COMPOSE_DEBUG_FILE := deploy/docker/docker-compose.debug.yml
ENV_FILE := deploy/docker/.env

.PHONY: run dev down clean logs ps seed users coraza-build \
        eval-up eval-down eval-clean eval-ftw eval-zap eval-nuclei eval-load eval-metrics eval-all eval-results

run:
	docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) up --build -d

dev:
	docker-compose -f $(COMPOSE_FILE) -f $(COMPOSE_DEBUG_FILE) --env-file $(ENV_FILE) up --build

down:
	docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) down

clean:
	docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) down -v

logs:
	docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) logs -f

ps:
	docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) ps

seed:
	docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec backend /app/.venv/bin/python scripts/seed_admin.py

users:
	docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec backend /app/.venv/bin/python scripts/manage_users.py $(ARGS)

coraza-build:
	docker build -f deploy/docker/coraza.Dockerfile -t guard-proxy/coraza-spoa:dev .

# ── Evaluation lab (delegates to benchmarks/Makefile) ─────────────────────
# See benchmarks/Makefile for full documentation and variable overrides.

eval-up:
	$(MAKE) -C benchmarks lab-up

eval-down:
	$(MAKE) -C benchmarks lab-down

eval-clean:
	$(MAKE) -C benchmarks lab-clean

eval-ftw:
	$(MAKE) -C benchmarks eval-ftw RUN_ID=$(RUN_ID) TARGET_VHOST=$(TARGET_VHOST)

eval-zap:
	$(MAKE) -C benchmarks eval-zap RUN_ID=$(RUN_ID) TARGET_VHOST=$(TARGET_VHOST)

eval-nuclei:
	$(MAKE) -C benchmarks eval-nuclei RUN_ID=$(RUN_ID) TARGET_VHOST=$(TARGET_VHOST)

eval-load:
	$(MAKE) -C benchmarks eval-load RUN_ID=$(RUN_ID) TARGET_VHOST=$(TARGET_VHOST)

eval-metrics:
	$(MAKE) -C benchmarks eval-metrics RUN_ID=$(RUN_ID)

eval-all:
	$(MAKE) -C benchmarks eval-all RUN_ID=$(RUN_ID) TARGET_VHOST=$(TARGET_VHOST)

eval-results:
	$(MAKE) -C benchmarks results RUN_ID=$(RUN_ID)
