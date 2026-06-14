#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/deploy/docker/docker-compose.yml"
ENV_FILE="${REPO_ROOT}/deploy/docker/.env"
CRS_RULES_DIR="${REPO_ROOT}/configs/coraza/crs/rules"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-120}"
SMOKE_PROJECT="${SMOKE_PROJECT:-guard-proxy-smoke-${RANDOM}-${RANDOM}}"
HOST_HEADER="${HOST_HEADER:-app.local}"
HAPROXY_HTTP_PORT="${HAPROXY_HTTP_PORT:-$((20000 + RANDOM % 40000))}"
export HAPROXY_HTTP_PORT
HAPROXY_BASE_URL="http://127.0.0.1:${HAPROXY_HTTP_PORT}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Copy deploy/docker/.env.example to deploy/docker/.env first." >&2
  exit 1
fi

if [[ ! -d "${CRS_RULES_DIR}" ]]; then
  echo "Missing CRS submodule content. Run 'git submodule update --init --recursive' first." >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" --project-name "${SMOKE_PROJECT}")
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" --project-name "${SMOKE_PROJECT}")
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

  "${COMPOSE[@]}" down -v || true
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
      --header "Host: ${HOST_HEADER}" \
      "${url}"
  )"

  if [[ "${actual}" != "${expected}" ]]; then
    echo "${description}: expected HTTP ${expected}, got ${actual}." >&2
    return 1
  fi

  echo "${description}: got HTTP ${actual}."
}

assert_header() {
  local description="$1"
  local expected="$2"
  local url="$3"
  local headers

  headers="$(
    curl \
      --silent \
      --show-error \
      --output /dev/null \
      --dump-header - \
      --header "Host: ${HOST_HEADER}" \
      "${url}"
  )"

  if ! grep -Fqi "${expected}" <<<"${headers}"; then
    echo "${description}: expected response header containing '${expected}'." >&2
    echo "${headers}" >&2
    return 1
  fi

  echo "${description}: found '${expected}'."
}

wait_for_header() {
  local description="$1"
  local expected="$2"
  local url="$3"
  local timeout="${4:-20}"
  local deadline=$((SECONDS + timeout))
  local headers=""

  echo "Waiting for ${description}..."
  while (( SECONDS < deadline )); do
    headers="$(
      curl \
        --silent \
        --show-error \
        --output /dev/null \
        --dump-header - \
        --header "Host: ${HOST_HEADER}" \
        --max-time 2 \
        "${url}" \
        2>/dev/null || true
    )"

    if grep -Fqi "${expected}" <<<"${headers}"; then
      echo "${description}: found '${expected}'."
      return 0
    fi

    sleep 1
  done

  echo "${description}: timed out waiting for response header containing '${expected}'." >&2
  if [[ -n "${headers}" ]]; then
    echo "${headers}" >&2
  fi
  return 1
}

cd "${REPO_ROOT}"

echo "Starting smoke stack '${SMOKE_PROJECT}' on ${HAPROXY_BASE_URL}..."
"${COMPOSE[@]}" up -d --build postgres backend coraza haproxy

wait_for_healthy postgres
wait_for_healthy backend
wait_for_healthy coraza
wait_for_healthy haproxy

assert_status "Benign request through WAF" "200" "${HAPROXY_BASE_URL}/docs"
assert_status "SQL injection request" "403" "${HAPROXY_BASE_URL}/?id=1%27%20OR%20%271%27%3D%271"

"${COMPOSE[@]}" stop coraza
# Wait until HAProxy starts returning the explicit unavailable reason.
wait_for_header "Coraza unavailable transition" "X-WAF-Degraded-Reason: coraza-unavailable" "${HAPROXY_BASE_URL}/" 20

assert_status "Degraded request without Coraza" "503" "${HAPROXY_BASE_URL}/"
assert_header "Degraded WAF status header" "X-WAF-Status: degraded" "${HAPROXY_BASE_URL}/"
assert_header "Degraded WAF reason header" "X-WAF-Degraded-Reason: coraza-unavailable" "${HAPROXY_BASE_URL}/"
assert_status "Health bypass while Coraza is stopped" "200" "${HAPROXY_BASE_URL}/health"

echo "E2E smoke test passed."
