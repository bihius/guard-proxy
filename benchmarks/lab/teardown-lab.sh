#!/usr/bin/env bash
# teardown-lab.sh — Stop and optionally remove the evaluation lab stack.
#
# Usage:
#   ./benchmarks/lab/teardown-lab.sh          # stop containers, keep volumes
#   ./benchmarks/lab/teardown-lab.sh --clean  # stop + remove all volumes

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
CORE_COMPOSE="${REPO_ROOT}/docker/docker-compose.yml"
TARGETS_COMPOSE="${SCRIPT_DIR}/docker-compose.targets.yml"
CORE_ENV="${REPO_ROOT}/docker/.env"
LAB_ENV="${SCRIPT_DIR}/.env"

CLEAN=false
for arg in "$@"; do
  case "$arg" in --clean) CLEAN=true ;; esac
done

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose -f "${CORE_COMPOSE}" -f "${TARGETS_COMPOSE}")
  [[ -f "${CORE_ENV}" ]] && COMPOSE+=(--env-file "${CORE_ENV}")
  [[ -f "${LAB_ENV}" ]] && COMPOSE+=(--env-file "${LAB_ENV}")
else
  COMPOSE=(docker-compose -f "${CORE_COMPOSE}" -f "${TARGETS_COMPOSE}")
fi

if [[ "${CLEAN}" == true ]]; then
  echo "Stopping lab and removing all volumes..."
  "${COMPOSE[@]}" down -v
else
  echo "Stopping lab (volumes preserved)..."
  "${COMPOSE[@]}" down
fi
