DOCKER_COMPOSE ?= $(shell command -v docker-compose >/dev/null 2>&1 && echo "docker-compose" || echo "docker compose")

COMPOSE_FILE := deploy/docker/docker-compose.yml
COMPOSE_DEBUG_FILE := deploy/docker/docker-compose.debug.yml
ENV_FILE := deploy/docker/.env

.PHONY: run dev down clean logs ps seed users coraza-build \
        eval-up eval-down eval-clean eval-ftw eval-corpus eval-zap eval-nuclei eval-load eval-metrics eval-all eval-results

run:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) --env-file $(ENV_FILE) up --build -d

dev:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) -f $(COMPOSE_DEBUG_FILE) --env-file $(ENV_FILE) up --build

down:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) --env-file $(ENV_FILE) down

clean:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) --env-file $(ENV_FILE) down -v

logs:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) --env-file $(ENV_FILE) logs -f

ps:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) --env-file $(ENV_FILE) ps

seed:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec backend /app/.venv/bin/python scripts/seed_admin.py

ifeq (users,$(firstword $(MAKECMDGOALS)))
  USERS_ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
  $(eval $(USERS_ARGS):;@:)
endif

users:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec backend /app/.venv/bin/python scripts/manage_users.py $(if $(USERS_ARGS),$(USERS_ARGS),$(ARGS))

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
	$(MAKE) -C benchmarks eval-ftw \
	  $(if $(RUN_ID),RUN_ID=$(RUN_ID)) \
	  $(if $(TARGET_VHOST),TARGET_VHOST=$(TARGET_VHOST))

eval-corpus:
	$(MAKE) -C benchmarks eval-corpus \
	  $(if $(RUN_ID),RUN_ID=$(RUN_ID)) \
	  $(if $(TARGET_VHOST),TARGET_VHOST=$(TARGET_VHOST))

eval-zap:
	$(MAKE) -C benchmarks eval-zap \
	  $(if $(RUN_ID),RUN_ID=$(RUN_ID)) \
	  $(if $(TARGET_VHOST),TARGET_VHOST=$(TARGET_VHOST))

eval-nuclei:
	$(MAKE) -C benchmarks eval-nuclei \
	  $(if $(RUN_ID),RUN_ID=$(RUN_ID)) \
	  $(if $(TARGET_VHOST),TARGET_VHOST=$(TARGET_VHOST))

eval-load:
	$(MAKE) -C benchmarks eval-load \
	  $(if $(RUN_ID),RUN_ID=$(RUN_ID)) \
	  $(if $(TARGET_VHOST),TARGET_VHOST=$(TARGET_VHOST))

eval-metrics:
	$(MAKE) -C benchmarks eval-metrics \
	  $(if $(RUN_ID),RUN_ID=$(RUN_ID))

eval-all:
	$(MAKE) -C benchmarks eval-all \
	  $(if $(RUN_ID),RUN_ID=$(RUN_ID)) \
	  $(if $(TARGET_VHOST),TARGET_VHOST=$(TARGET_VHOST))

eval-results:
	$(MAKE) -C benchmarks results \
	  $(if $(RUN_ID),RUN_ID=$(RUN_ID))
