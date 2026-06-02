REPO_ROOT    := $(shell git rev-parse --show-toplevel 2>/dev/null || pwd)
DEMO_COMPOSE := $(REPO_ROOT)/deploy/demo/docker-compose.yml
LAB_COMPOSE  := $(REPO_ROOT)/benchmarks/lab/docker-compose.targets.yml
DEMO_ENV     := $(REPO_ROOT)/deploy/demo/.env
LAB_ENV      := $(REPO_ROOT)/benchmarks/lab/.env
RUNNERS      := $(REPO_ROOT)/benchmarks/lab/runners

RUN_ID       ?= $(shell date +%Y%m%d-%H%M%S)
TARGET_VHOST ?= juice.local
DIRECT_HOST  ?= juiceshop
DIRECT_PORT  ?= 3000

.PHONY: lab-up lab-down lab-clean \
        eval-ftw eval-zap eval-nuclei eval-load eval-metrics eval-all \
        results help

# ── Lab lifecycle ──────────────────────────────────────────────────────────

## Bring up the demo + all lab targets and register vhosts.
lab-up:
	@echo "==> Starting guard-proxy demo + lab targets..."
	docker compose \
	  -f $(DEMO_COMPOSE) \
	  -f $(LAB_COMPOSE) \
	  --env-file $(DEMO_ENV) \
	  --env-file $(LAB_ENV) \
	  up -d --build
	@echo "==> Seeding vhosts..."
	bash $(REPO_ROOT)/deploy/demo/setup-demo.sh
	bash $(REPO_ROOT)/benchmarks/lab/setup-lab.sh --skip-compose

## Stop the lab (preserve volumes).
lab-down:
	bash $(REPO_ROOT)/benchmarks/lab/teardown-lab.sh

## Stop the lab and remove all volumes.
lab-clean:
	bash $(REPO_ROOT)/benchmarks/lab/teardown-lab.sh --clean

# ── Individual scenario runners ────────────────────────────────────────────

## CRS regression suite (TPR gold standard). Uses go-ftw against the CRS corpus.
eval-ftw:
	@mkdir -p $(REPO_ROOT)/benchmarks/results/run-$(RUN_ID)/ftw
	RUN_ID=$(RUN_ID) TARGET_VHOST=$(TARGET_VHOST) \
	  bash $(RUNNERS)/run-ftw.sh

## ZAP baseline scan (FPR measurement, WordPress is best target for FP).
eval-zap:
	@mkdir -p $(REPO_ROOT)/benchmarks/results/run-$(RUN_ID)/zap-$(TARGET_VHOST)
	RUN_ID=$(RUN_ID) TARGET_VHOST=$(TARGET_VHOST) \
	  bash $(RUNNERS)/run-zap.sh

## Nuclei CVE templates (WAF TPR against real attack payloads).
eval-nuclei:
	@mkdir -p $(REPO_ROOT)/benchmarks/results/run-$(RUN_ID)/nuclei-$(TARGET_VHOST)
	RUN_ID=$(RUN_ID) TARGET_VHOST=$(TARGET_VHOST) \
	  bash $(RUNNERS)/run-nuclei.sh

## Latency + RPS load test (WAF vs direct). Measures overhead.
eval-load:
	@mkdir -p $(REPO_ROOT)/benchmarks/results/run-$(RUN_ID)/load-$(TARGET_VHOST)
	RUN_ID=$(RUN_ID) TARGET_VHOST=$(TARGET_VHOST) \
	  DIRECT_HOST=$(DIRECT_HOST) DIRECT_PORT=$(DIRECT_PORT) \
	  bash $(RUNNERS)/run-load.sh

## Aggregate all scenario outputs into results.csv + report.json.
eval-metrics:
	RUN_ID=$(RUN_ID) bash $(RUNNERS)/collect-metrics.sh

## Run all scenarios (ftw → zap → nuclei → load → metrics) in one pass.
eval-all: eval-ftw eval-zap eval-nuclei eval-load eval-metrics

# ── Results summary ────────────────────────────────────────────────────────

## Print a summary of the most recent run (or RUN_ID= a specific run).
results:
	@latest=$$(ls -1t $(REPO_ROOT)/benchmarks/results/ 2>/dev/null | head -1); \
	run=$${RUN_ID:-$$latest}; \
	csv="$(REPO_ROOT)/benchmarks/results/run-$${run}/results.csv"; \
	if [[ -f "$$csv" ]]; then \
	  echo "Run: $${run}"; column -t -s, "$$csv"; \
	else \
	  echo "No results found. Run 'make eval-all RUN_ID=<id>' first."; \
	fi

# ── Help ───────────────────────────────────────────────────────────────────

help:
	@echo "Guard Proxy Evaluation Lab"
	@echo ""
	@echo "Setup:"
	@echo "  cp deploy/demo/.env.example deploy/demo/.env"
	@echo "  cp benchmarks/lab/.env.example benchmarks/lab/.env"
	@echo "  git submodule update --init --recursive"
	@echo ""
	@echo "Targets:"
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/^## /  /'
	@echo ""
	@echo "Variables:"
	@echo "  RUN_ID=<id>         Override run ID (default: timestamp)"
	@echo "  TARGET_VHOST=<host> Target vhost (default: juice.local)"
	@echo "  DIRECT_HOST=<name>  Direct-access Docker service name"
	@echo "  DIRECT_PORT=<port>  Direct-access port (bypasses HAProxy)"
	@echo ""
	@echo "Example (3 runs for thesis median):"
	@echo "  for i in 1 2 3; do make eval-all; done"
