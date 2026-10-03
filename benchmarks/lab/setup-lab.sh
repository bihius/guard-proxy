#!/usr/bin/env bash
# setup-lab.sh — Bring up the evaluation lab and register all target vhosts.
#
# Extends the real Guard Proxy stack with two targets — WordPress (wp.local)
# and Albedo (ftw.local) — gives each target vhost its own WAF policy
# ("Lab <domain>", PL1 profile), wires each domain through HAProxy via the
# guard-proxy backend API, and installs WordPress.
#
# Prerequisites:
#   - docker/.env (copy from docker/.env.example)
#   - benchmarks/lab/.env (copy from benchmarks/lab/.env.example)
#   - CRS submodule initialised: git submodule update --init --recursive
#   - Docker with Docker Compose v2
#
# Usage: ./benchmarks/lab/setup-lab.sh [--skip-compose]

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
CORE_COMPOSE="${REPO_ROOT}/docker/docker-compose.yml"
TARGETS_COMPOSE="${SCRIPT_DIR}/docker-compose.targets.yml"
CORE_ENV="${REPO_ROOT}/docker/.env"
LAB_ENV="${SCRIPT_DIR}/.env"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-240}"
SKIP_COMPOSE=false

for arg in "$@"; do
  case "$arg" in
    --skip-compose) SKIP_COMPOSE=true ;;
  esac
done

for f in "${CORE_ENV}" "${LAB_ENV}"; do
  if [[ ! -f "${f}" ]]; then
    echo "Missing ${f}. Copy the matching .env.example first." >&2
    exit 1
  fi
done

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose -f "${CORE_COMPOSE}" -f "${TARGETS_COMPOSE}" --env-file "${CORE_ENV}" --env-file "${LAB_ENV}")
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose -f "${CORE_COMPOSE}" -f "${TARGETS_COMPOSE}" --env-file "${CORE_ENV}" --env-file "${LAB_ENV}")
else
  echo "Docker Compose is required." >&2
  exit 1
fi

# ── Helpers ────────────────────────────────────────────────────────────────

env_value() {
  local name="$1"
  local fallback="${2:-}"
  local value
  value="$(grep -E "^${name}=" "${CORE_ENV}" "${LAB_ENV}" 2>/dev/null | tail -n 1 | cut -d= -f2- || true)"
  if [[ -z "${value}" ]]; then printf '%s' "${fallback}"; else printf '%s' "${value}"; fi
}

json_string() {
  python3 -c 'import json, sys; print(json.dumps(sys.argv[1]))' "$1"
}

api_json() {
  local method="$1"; local path="$2"; local token="${3:-}"; local body="${4:-}"
  local response_file http_code
  response_file="$(mktemp)"
  if [[ -n "${body}" ]]; then
    http_code="$(curl --silent --show-error --output "${response_file}" --write-out '%{http_code}' \
      --request "${method}" --header "Content-Type: application/json" \
      ${token:+--header "Authorization: Bearer ${token}"} --data "${body}" "${API_BASE_URL}${path}")"
  else
    http_code="$(curl --silent --show-error --output "${response_file}" --write-out '%{http_code}' \
      --request "${method}" ${token:+--header "Authorization: Bearer ${token}"} "${API_BASE_URL}${path}")"
  fi
  if [[ "${http_code}" -lt 200 || "${http_code}" -ge 300 ]]; then
    echo "API ${method} ${path} failed with HTTP ${http_code}:" >&2
    cat "${response_file}" >&2; rm -f "${response_file}"; return 1
  fi
  cat "${response_file}"; rm -f "${response_file}"
}

health_status() {
  local service="$1"; local id
  id="$("${COMPOSE[@]}" ps -q "${service}" 2>/dev/null || true)"
  if [[ -z "${id}" ]]; then echo "missing"; return; fi
  docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${id}"
}

wait_for_healthy() {
  local service="$1"; local deadline=$((SECONDS + TIMEOUT_SECONDS)); local status
  echo "Waiting for ${service}..."
  while (( SECONDS < deadline )); do
    status="$(health_status "${service}")"
    case "${status}" in
      healthy) echo "${service} is healthy."; return 0 ;;
      exited|dead) echo "${service} is ${status}." >&2; return 1 ;;
    esac
    sleep 3
  done
  echo "Timed out waiting for ${service}; last status: ${status:-unknown}." >&2; return 1
}

ensure_crs_bundle() {
  if compgen -G "${REPO_ROOT}/configs/coraza/crs/rules/*.conf" >/dev/null; then return; fi
  echo "Missing OWASP CRS rules in configs/coraza/crs." >&2
  echo "Run: git submodule update --init --recursive" >&2; exit 1
}

# shellcheck source=benchmarks/lab/policy-profiles.sh
source "${SCRIPT_DIR}/policy-profiles.sh"

ensure_policy() {
  local name="$1"; local body="$2"
  echo "Ensuring WAF policy '${name}' exists..." >&2
  local response
  response="$(api_json POST /policies "${token}" "${body}" || true)"
  if [[ -z "${response}" ]]; then
    response="$(api_json GET /policies "${token}")"
  fi
  POLICY_NAME="${name}" POLICY_RESPONSE="${response}" python3 - <<'PY'
import json, sys, os
data = json.loads(os.environ["POLICY_RESPONSE"])
name = os.environ["POLICY_NAME"]
if isinstance(data, dict) and "items" in data:
    items = data["items"]
elif isinstance(data, list):
    items = data
else:
    items = [data]
for item in items:
    if item["name"] == name:
        print(item["id"]); sys.exit(0)
sys.exit(f"Policy '{name}' not found after create/list")
PY
}

ensure_vhost() {
  local domain="$1"; local backend_url="$2"; local description="$3"; local policy_id="$4"
  local vhost_body vhost_response vhost_id
  vhost_body="$(printf '{"domain":%s,"backend_url":%s,"description":%s,"ssl_enabled":false,"is_active":true,"policy_id":%s}' \
    "$(json_string "${domain}")" "$(json_string "${backend_url}")" \
    "$(json_string "${description}")" "${policy_id}")"
  vhost_response="$(api_json POST /vhosts "${token}" "${vhost_body}" || true)"
  if [[ -n "${vhost_response}" ]]; then return; fi
  local vhosts_response
  vhosts_response="$(api_json GET /vhosts "${token}")"
  vhost_id="$(VHOSTS="${vhosts_response}" DOMAIN="${domain}" python3 - <<'PY'
import json, os
data = json.loads(os.environ["VHOSTS"]); domain = os.environ["DOMAIN"]
items = data["items"] if isinstance(data, dict) and "items" in data else data
for item in items:
    if item["domain"] == domain:
        print(item["id"]); exit(0)
exit(f"vhost {domain!r} not found")
PY
  )"
  api_json PATCH "/vhosts/${vhost_id}" "${token}" "${vhost_body}" >/dev/null
}

# ── Main ───────────────────────────────────────────────────────────────────

ensure_crs_bundle

if [[ "${SKIP_COMPOSE}" == false ]]; then
  echo "Starting Guard Proxy + lab target stack..."
  "${COMPOSE[@]}" up -d --build --remove-orphans

  wait_for_healthy backend
  wait_for_healthy coraza
  wait_for_healthy haproxy
  wait_for_healthy wordpress
fi

ADMIN_EMAIL="$(env_value ADMIN_EMAIL admin@example.com)"
ADMIN_PASSWORD="$(env_value ADMIN_PASSWORD GuardProxyDemo12345)"
BACKEND_HTTP_PORT="$(env_value BACKEND_HTTP_PORT 8000)"
HAPROXY_HTTP_PORT="$(env_value HAPROXY_HTTP_PORT 8080)"
API_BASE_URL="http://127.0.0.1:${BACKEND_HTTP_PORT}"
WAF_BASE_URL="http://127.0.0.1:${HAPROXY_HTTP_PORT}"

echo "Logging in..."
login_body="$(printf '{"email":%s,"password":%s}' "$(json_string "${ADMIN_EMAIL}")" "$(json_string "${ADMIN_PASSWORD}")")"
token="$(api_json POST /auth/login "" "${login_body}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"

# ── Per-vhost policies and vhosts ──────────────────────────────────────────

load_policy_profile pl1

LAB_FTW_DOMAIN="$(env_value LAB_FTW_DOMAIN ftw.local)"
LAB_FTW_BACKEND_URL="$(env_value LAB_FTW_BACKEND_URL http://ftw-backend:8080)"
LAB_WP_DOMAIN="$(env_value LAB_WP_DOMAIN wp.local)"
LAB_WP_BACKEND_URL="$(env_value LAB_WP_BACKEND_URL http://wordpress:80)"

ensure_lab_vhost() {
  local domain="$1"; local backend_url="$2"; local description="$3"
  local name policy_body policy_id
  name="$(lab_policy_name "${domain}")"
  policy_body="$(printf '{"name":%s,"description":%s,"paranoia_level":%s,"inbound_anomaly_threshold":%s,"outbound_anomaly_threshold":%s,"enforcement_mode":"block"}' \
    "$(json_string "${name}")" "$(json_string "Lab evaluation policy for ${domain}")" \
    "${PROFILE_PARANOIA}" "${PROFILE_INBOUND_THRESHOLD}" "${PROFILE_OUTBOUND_THRESHOLD}")"
  policy_id="$(ensure_policy "${name}" "${policy_body}")"
  ensure_vhost "${domain}" "${backend_url}" "${description}" "${policy_id}"
}

echo "Registering lab vhosts (${LAB_FTW_DOMAIN}, ${LAB_WP_DOMAIN}), one policy each..."
ensure_lab_vhost "${LAB_FTW_DOMAIN}" "${LAB_FTW_BACKEND_URL}" "Albedo — CRS go-ftw regression and load-test backend"
ensure_lab_vhost "${LAB_WP_DOMAIN}" "${LAB_WP_BACKEND_URL}" "WordPress — tagged corpus target (no CRS exclusions)"

# Resets policies that already existed (e.g. left on PL2 by a sweep) to PL1
# and applies the generated HAProxy/Coraza config.
POLICY=pl1 TARGET_VHOST= bash "${SCRIPT_DIR}/set-policy.sh"

# ── WordPress installation (idempotent) ────────────────────────────────────
# Without it every WordPress URL redirects to the installer, and the corpus
# would measure the installer instead of a real site.
echo "Installing WordPress (skipped when already installed)..."
"${COMPOSE[@]}" run --rm wp-cli

echo
echo "Eval lab ready: ${LAB_FTW_DOMAIN}, ${LAB_WP_DOMAIN} via ${WAF_BASE_URL} (curl -H 'Host: <domain>')."
echo "Smoke (expect 403): curl -si -H 'Host: ${LAB_WP_DOMAIN}' '${WAF_BASE_URL}/?q=1+UNION+SELECT+1--' | grep 'HTTP/'"
