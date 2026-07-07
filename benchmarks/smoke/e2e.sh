#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker/docker-compose.yml"
ENV_FILE="${REPO_ROOT}/docker/.env"
CRS_RULES_DIR="${REPO_ROOT}/configs/coraza/crs/rules"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-120}"
SMOKE_PROJECT="${SMOKE_PROJECT:-guard-proxy-smoke-${RANDOM}-${RANDOM}}"
# Must be one of the hosts accepted by the host_app ACL in
# configs/haproxy/haproxy.cfg, otherwise HAProxy responds with 421.
HOST_HEADER="${HOST_HEADER:-app.local}"
HAPROXY_HTTP_PORT="${HAPROXY_HTTP_PORT:-$((20000 + RANDOM % 40000))}"
HAPROXY_HTTPS_PORT="${HAPROXY_HTTPS_PORT:-$((20000 + RANDOM % 40000))}"
export HAPROXY_HTTP_PORT
export HAPROXY_HTTPS_PORT
HAPROXY_BASE_URL="http://127.0.0.1:${HAPROXY_HTTP_PORT}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Copy docker/.env.example to docker/.env first." >&2
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

# Like assert_status, but retries until the expected status is observed or
# the timeout elapses. Needed right after a config apply: HAProxy reloads its
# routing ACLs synchronously, but Coraza's supervisor only restarts
# coraza-spoa with the new crs-setup.conf on its next 1s poll tick (see
# docker/coraza-supervisor.sh), so a request fired immediately after
# /config/apply can still hit the previous (pre-policy, DetectionOnly) engine.
wait_for_status() {
  local description="$1"
  local expected="$2"
  local url="$3"
  local timeout="${4:-30}"
  local deadline=$((SECONDS + timeout))
  local actual=""

  while (( SECONDS < deadline )); do
    actual="$(
      curl \
        --silent \
        --show-error \
        --output /dev/null \
        --write-out '%{http_code}' \
        --header "Host: ${HOST_HEADER}" \
        --max-time 5 \
        "${url}" \
        2>/dev/null || true
    )"

    if [[ "${actual}" == "${expected}" ]]; then
      echo "${description}: got HTTP ${actual}."
      return 0
    fi

    sleep 1
  done

  echo "${description}: expected HTTP ${expected}, got ${actual} after ${timeout}s." >&2
  return 1
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

SMOKE_ADMIN_EMAIL="smoke-admin@example.com"
SMOKE_ADMIN_PASSWORD="smoke-admin-password-123"

# Runs an HTTP request against the backend's own port from inside the
# backend container (bypassing HAProxy, which has no usable ACL yet at
# this point) and prints the JSON response body to stdout.
backend_api() {
  local method="$1"
  local path="$2"
  local token="${3:-}"
  local payload="${4:-}"

  REQ_METHOD="${method}" REQ_PATH="${path}" REQ_TOKEN="${token}" REQ_PAYLOAD="${payload}" \
    "${COMPOSE[@]}" exec -T -e REQ_METHOD -e REQ_PATH -e REQ_TOKEN -e REQ_PAYLOAD backend python3 -c '
import json
import os
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

method = os.environ["REQ_METHOD"]
path = os.environ["REQ_PATH"]
token = os.environ.get("REQ_TOKEN") or None
payload_raw = os.environ.get("REQ_PAYLOAD") or ""

headers = {"Accept": "application/json"}
body = None
if payload_raw:
    body = payload_raw.encode("utf-8")
    headers["Content-Type"] = "application/json"
if token:
    headers["Authorization"] = "Bearer " + token

request = Request("http://127.0.0.1:8000" + path, data=body, headers=headers, method=method)
try:
    with urlopen(request, timeout=10) as resp:
        sys.stdout.write(resp.read().decode("utf-8"))
except HTTPError as exc:
    sys.stderr.write(exc.read().decode("utf-8"))
    sys.exit(1)
'
}

setup_vhost_and_apply_config() {
  echo "Seeding admin user and a vhost so HAProxy has a routable host ACL..."
  "${COMPOSE[@]}" exec -T backend /app/.venv/bin/python scripts/seed_admin.py \
    --email "${SMOKE_ADMIN_EMAIL}" \
    --password "${SMOKE_ADMIN_PASSWORD}" \
    --full-name "Smoke Test Admin"

  local token
  token="$(
    backend_api POST /auth/login "" \
      "$(printf '{"email":"%s","password":"%s"}' "${SMOKE_ADMIN_EMAIL}" "${SMOKE_ADMIN_PASSWORD}")" \
      | python3 -c 'import json, sys; print(json.load(sys.stdin)["access_token"])'
  )"

  local policy_id
  policy_id="$(
    backend_api POST /policies "${token}" \
      '{"name":"Smoke test policy","paranoia_level":1,"inbound_anomaly_threshold":5,"outbound_anomaly_threshold":4,"enforcement_mode":"block"}' \
      | python3 -c 'import json, sys; print(json.load(sys.stdin)["id"])'
  )"

  backend_api POST /vhosts "${token}" \
    "$(printf '{"domain":"%s","backend_url":"http://backend:8000","ssl_enabled":false,"is_active":true,"policy_id":%s}' "${HOST_HEADER}" "${policy_id}")" \
    >/dev/null

  backend_api POST /config/apply "${token}" "{}" >/dev/null
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

# A fresh database has no vhosts, so the generated HAProxy config has no
# host-routing ACL and denies every non-ACME request with 421. Create a
# policy + vhost and apply the config so HAProxy reloads with a real route
# for HOST_HEADER before running the WAF assertions below.
setup_vhost_and_apply_config

assert_status "Benign request through WAF" "200" "${HAPROXY_BASE_URL}/docs"
wait_for_status "SQL injection request" "403" "${HAPROXY_BASE_URL}/?id=1%27%20OR%20%271%27%3D%271" 30

"${COMPOSE[@]}" stop coraza
# Wait until HAProxy starts returning the explicit unavailable reason.
wait_for_header "Coraza unavailable transition" "X-WAF-Degraded-Reason: coraza-unavailable" "${HAPROXY_BASE_URL}/" 20

assert_status "Degraded request without Coraza" "503" "${HAPROXY_BASE_URL}/"
assert_header "Degraded WAF status header" "X-WAF-Status: degraded" "${HAPROXY_BASE_URL}/"
assert_header "Degraded WAF reason header" "X-WAF-Degraded-Reason: coraza-unavailable" "${HAPROXY_BASE_URL}/"
assert_status "Health bypass while Coraza is stopped" "200" "${HAPROXY_BASE_URL}/health"

echo "E2E smoke test passed."
