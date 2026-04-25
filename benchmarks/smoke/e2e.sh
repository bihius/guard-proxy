#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/deploy/docker/docker-compose.yml"
ENV_FILE="${REPO_ROOT}/deploy/docker/.env"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-120}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Copy deploy/docker/.env.example to deploy/docker/.env first." >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}")
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}")
else
  echo "Docker Compose is required." >&2
  exit 1
fi

cleanup() {
  local status=$?

  if [[ "${status}" -ne 0 ]]; then
    echo
    echo "Smoke test failed. Recent HAProxy and Coraza logs:"
    "${COMPOSE[@]}" logs --tail=50 haproxy coraza || true
  fi

  "${COMPOSE[@]}" down -v
  exit "${status}"
}
trap cleanup EXIT

container_id() {
  local service="$1"
  "${COMPOSE[@]}" ps -q "${service}"
}

health_status() {
  local service="$1"
  local id

  id="$(container_id "${service}")"
  if [[ -z "${id}" ]]; then
    echo "missing"
    return
  fi

  docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${id}"
}

wait_for_healthy() {
  local service="$1"
  local deadline=$((SECONDS + TIMEOUT_SECONDS))
  local status

  echo "Waiting for ${service} to become healthy..."
  while (( SECONDS < deadline )); do
    status="$(health_status "${service}")"
    case "${status}" in
      healthy)
        echo "${service} is healthy."
        return 0
        ;;
      exited|dead)
        echo "${service} is ${status}." >&2
        return 1
        ;;
    esac

    sleep 2
  done

  echo "Timed out waiting for ${service}; last status: ${status:-unknown}." >&2
  return 1
}

assert_status() {
  local description="$1"
  local expected="$2"
  local url="$3"
  local actual

  actual="$(
    curl \
      --silent \
      --show-error \
      --output /dev/null \
      --write-out '%{http_code}' \
      --header 'Host: app.local' \
      "${url}"
  )"

  if [[ "${actual}" != "${expected}" ]]; then
    echo "${description}: expected HTTP ${expected}, got ${actual}." >&2
    return 1
  fi

  echo "${description}: got HTTP ${actual}."
}

cd "${REPO_ROOT}"

"${COMPOSE[@]}" up -d --build postgres backend coraza haproxy

wait_for_healthy backend
wait_for_healthy coraza
wait_for_healthy haproxy

assert_status "Benign request" "200" "http://127.0.0.1:8080/health"
assert_status "SQL injection request" "403" "http://127.0.0.1:8080/?id=1%27%20OR%20%271%27%3D%271"

echo "E2E smoke test passed."
