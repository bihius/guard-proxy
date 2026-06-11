REPO_ROOT    := $(shell git rev-parse --show-toplevel 2>/dev/null || pwd)
CORE_COMPOSE := $(REPO_ROOT)/deploy/docker/docker-compose.yml
LAB_COMPOSE  := $(REPO_ROOT)/benchmarks/lab/docker-compose.targets.yml
CORE_ENV     := $(REPO_ROOT)/deploy/docker/.env
LAB_ENV      := $(REPO_ROOT)/benchmarks/lab/.env
RUNNERS      := $(REPO_ROOT)/benchmarks/lab/runners
DOCKER_COMPOSE ?= $(shell command -v docker-compose >/dev/null 2>&1 && echo "docker-compose" || echo "docker compose")
COMPOSE      := $(DOCKER_COMPOSE) -f $(CORE_COMPOSE) -f $(LAB_COMPOSE) --env-file $(CORE_ENV) --env-file $(LAB_ENV)

RUN_ID       ?= $(shell date +%Y%m%d-%H%M%S)
TARGET_VHOST ?=
DIRECT_HOST  ?= juiceshop
DIRECT_PORT  ?= 3000

# POLICY selects which WAF policy is active for the run: pl1 (baseline, default)
# or pl2 (high-paranoia sweep, see benchmarks/lab/.env.example LAB_PL2_POLICY_*).
POLICY       ?= pl1
# Each policy pass gets its own results directory: run-<RUN_ID>-pl1 / run-<RUN_ID>-pl2.
EFFECTIVE_RUN_ID := $(RUN_ID)-$(POLICY)

.PHONY: lab-up lab-down lab-clean \
        eval-ftw eval-corpus eval-zap eval-nuclei eval-load eval-metrics eval-all \
        set-policy eval-sweep \
        results help

# ── Lab lifecycle ──────────────────────────────────────────────────────────

## Bring up the real stack + all lab targets and register vhosts.
lab-up:
	@echo "==> Starting guard-proxy stack + lab targets..."
	@$(COMPOSE) up -d --build
	@echo "==> Seeding admin user..."
	@$(COMPOSE) exec -T backend /app/.venv/bin/python scripts/seed_admin.py
	@echo "==> Waiting for HAProxy master socket..."
	@$(COMPOSE) exec -T backend sh -c \
	  'deadline=$$((SECONDS+120)); \
	   until test -S /var/run/haproxy/master.sock; do \
	     if [ $$SECONDS -ge $$deadline ]; then echo "Timed out waiting for HAProxy master socket" >&2; exit 1; fi; \
	     sleep 2; \
	   done; echo "HAProxy master socket is ready."'
	@echo "==> Seeding vhosts..."
	@bash $(REPO_ROOT)/benchmarks/lab/setup-lab.sh --skip-compose

## Stop the lab (preserve volumes).
lab-down:
	bash $(REPO_ROOT)/benchmarks/lab/teardown-lab.sh

## Stop the lab and remove all volumes.
lab-clean:
	bash $(REPO_ROOT)/benchmarks/lab/teardown-lab.sh --clean

# ── Individual scenario runners ────────────────────────────────────────────

## CRS regression suite. Reports go-ftw CRS conformance, not TPR/FPR.
eval-ftw:
	@mkdir -p $(REPO_ROOT)/benchmarks/results/run-$(EFFECTIVE_RUN_ID)/ftw
	RUN_ID=$(EFFECTIVE_RUN_ID) POLICY=$(POLICY) TARGET_VHOST=$(if $(TARGET_VHOST),$(TARGET_VHOST),ftw.local) \
	  bash $(RUNNERS)/run-ftw.sh

## Tagged labeled benign/attack corpus (the only clean TP/FN/TN/FP source).
eval-corpus:
	@mkdir -p $(REPO_ROOT)/benchmarks/results/run-$(EFFECTIVE_RUN_ID)/corpus-$(if $(TARGET_VHOST),$(TARGET_VHOST),wp.local)
	RUN_ID=$(EFFECTIVE_RUN_ID) POLICY=$(POLICY) TARGET_VHOST=$(if $(TARGET_VHOST),$(TARGET_VHOST),wp.local) \
	  bash $(RUNNERS)/run-corpus.sh

## ZAP baseline scan (supplemental scanner-assisted WordPress coverage).
eval-zap:
	@mkdir -p $(REPO_ROOT)/benchmarks/results/run-$(EFFECTIVE_RUN_ID)/zap-$(if $(TARGET_VHOST),$(TARGET_VHOST),wp.local)
	RUN_ID=$(EFFECTIVE_RUN_ID) POLICY=$(POLICY) TARGET_VHOST=$(if $(TARGET_VHOST),$(TARGET_VHOST),wp.local) \
	  bash $(RUNNERS)/run-zap.sh

## Nuclei CVE templates (supplemental reached-app/bypass evidence).
eval-nuclei:
	@mkdir -p $(REPO_ROOT)/benchmarks/results/run-$(EFFECTIVE_RUN_ID)/nuclei-$(if $(TARGET_VHOST),$(TARGET_VHOST),juice.local)
	RUN_ID=$(EFFECTIVE_RUN_ID) POLICY=$(POLICY) TARGET_VHOST=$(if $(TARGET_VHOST),$(TARGET_VHOST),juice.local) \
	  bash $(RUNNERS)/run-nuclei.sh

## Latency + RPS load test (WAF vs direct). Measures overhead.
eval-load:
	@mkdir -p $(REPO_ROOT)/benchmarks/results/run-$(EFFECTIVE_RUN_ID)/load-$(if $(TARGET_VHOST),$(TARGET_VHOST),juice.local)
	RUN_ID=$(EFFECTIVE_RUN_ID) POLICY=$(POLICY) TARGET_VHOST=$(if $(TARGET_VHOST),$(TARGET_VHOST),juice.local) \
	  DIRECT_HOST=$(DIRECT_HOST) DIRECT_PORT=$(DIRECT_PORT) \
	  bash $(RUNNERS)/run-load.sh

## Aggregate all scenario outputs into results.csv + report.json.
eval-metrics:
	RUN_ID=$(EFFECTIVE_RUN_ID) bash $(RUNNERS)/collect-metrics.sh

## Run all scenarios (ftw → corpus → zap → nuclei → load → metrics) in one pass.
## POLICY=pl1 (default) or POLICY=pl2 selects the active WAF policy; results land
## in benchmarks/results/run-<RUN_ID>-<POLICY>/.
eval-all: eval-ftw eval-corpus eval-zap eval-nuclei eval-load eval-metrics

# ── Paranoia level sweep ────────────────────────────────────────────────────

## Switch all lab vhosts to the given POLICY (pl1|pl2) and reload HAProxy/Coraza config.
set-policy:
	POLICY=$(POLICY) bash $(REPO_ROOT)/benchmarks/lab/set-policy.sh

## Run the full eval suite at PL1, then switch to PL2 and run it again, sharing
## one base RUN_ID. Produces run-<id>-pl1/ and run-<id>-pl2/ for side-by-side comparison.
eval-sweep:
	@base_run_id=$(RUN_ID); \
	echo "==> PL1 pass (run-$${base_run_id}-pl1)"; \
	$(MAKE) set-policy POLICY=pl1; \
	$(MAKE) eval-all RUN_ID=$${base_run_id} POLICY=pl1; \
	echo "==> PL2 pass (run-$${base_run_id}-pl2)"; \
	$(MAKE) set-policy POLICY=pl2; \
	$(MAKE) eval-all RUN_ID=$${base_run_id} POLICY=pl2; \
	echo "==> Done. Results for PL1 pass:"; \
	$(MAKE) results RUN_ID=$${base_run_id} POLICY=pl1; \
	echo ""; \
	echo "==> Results for PL2 pass:"; \
	$(MAKE) results RUN_ID=$${base_run_id} POLICY=pl2

# ── Results summary ────────────────────────────────────────────────────────

## Print a summary of the most recent run (or RUN_ID=<id> [POLICY=pl1|pl2] for a specific run).
results:
	@if [ "$(origin RUN_ID)" = "command line" ]; then \
	  run="$(EFFECTIVE_RUN_ID)"; \
	else \
	  run=$$(ls -1t $(REPO_ROOT)/benchmarks/results/ 2>/dev/null \
	          | grep '^run-' | head -1 | sed 's/^run-//'); \
	fi; \
	csv="$(REPO_ROOT)/benchmarks/results/run-$${run}/results.csv"; \
	if [ -f "$$csv" ]; then \
	  echo "Run: $${run}"; column -t -s, "$$csv"; \
	else \
	  echo "No results found for run-$${run}. Run 'make eval-all RUN_ID=<id> [POLICY=pl1|pl2]' first."; \
	fi

# ── Help ───────────────────────────────────────────────────────────────────

help:
	@echo "Guard Proxy Evaluation Lab"
	@echo ""
	@echo "Setup:"
	@echo "  cp deploy/docker/.env.example deploy/docker/.env"
	@echo "  cp benchmarks/lab/.env.example benchmarks/lab/.env"
	@echo "  git submodule update --init --recursive"
	@echo ""
	@echo "Targets:"
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/^## /  /'
	@echo ""
	@echo "Variables:"
	@echo "  RUN_ID=<id>         Override run ID (default: timestamp)"
	@echo "  POLICY=pl1|pl2      Active WAF policy (default: pl1). Results go to"
	@echo "                      benchmarks/results/run-<RUN_ID>-<POLICY>/."
	@echo "  TARGET_VHOST=<host> Override scenario vhost (defaults: ftw.local/wp.local/juice.local)"
	@echo "  DIRECT_HOST=<name>  Direct-access Docker service name"
	@echo "  DIRECT_PORT=<port>  Direct-access port (bypasses HAProxy)"
	@echo ""
	@echo "Example (3 runs for median):"
	@echo "  for i in 1 2 3; do make eval-all; done"
	@echo ""
	@echo "Example (PL1 vs PL2 sweep across all tools/targets):"
	@echo "  make eval-sweep"
