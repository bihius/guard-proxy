#!/usr/bin/env bash
# setup-lab.sh — Bring up the evaluation lab and register all target vhosts.
#
# Extends the real Guard Proxy stack with WordPress/Juice Shop/DVWA targets, seeds two
# WAF policies (baseline PL1 and high-paranoia PL2), and wires each target
# domain through HAProxy via the guard-proxy backend API.
#
# Prerequisites:
#   - deploy/docker/.env (copy from deploy/docker/.env.example)
#   - benchmarks/lab/.env (copy from benchmarks/lab/.env.example)
#   - CRS submodule initialised: git submodule update --init --recursive
#   - Docker with Docker Compose v2
#
# Usage: ./benchmarks/lab/setup-lab.sh [--skip-compose]

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
CORE_COMPOSE="${REPO_ROOT}/deploy/docker/docker-compose.yml"
TARGETS_COMPOSE="${SCRIPT_DIR}/docker-compose.targets.yml"
CORE_ENV="${REPO_ROOT}/deploy/docker/.env"
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
items = data if isinstance(data, list) else [data]
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
for item in data:
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
  "${COMPOSE[@]}" up -d --build

  wait_for_healthy backend
  wait_for_healthy coraza
  wait_for_healthy haproxy
  wait_for_healthy juiceshop
  wait_for_healthy dvwa
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

# ── Policies ───────────────────────────────────────────────────────────────

LAB_POLICY_NAME="$(env_value LAB_POLICY_NAME 'Lab Baseline')"
LAB_POLICY_PARANOIA="$(env_value LAB_POLICY_PARANOIA 1)"
LAB_POLICY_INBOUND_THRESHOLD="$(env_value LAB_POLICY_INBOUND_THRESHOLD 5)"

baseline_body="$(printf '{"name":%s,"description":"Lab evaluation baseline — PL%s anomaly threshold %s block","paranoia_level":%s,"inbound_anomaly_threshold":%s,"enforcement_mode":"block"}' \
  "$(json_string "${LAB_POLICY_NAME}")" "${LAB_POLICY_PARANOIA}" "${LAB_POLICY_INBOUND_THRESHOLD}" \
  "${LAB_POLICY_PARANOIA}" "${LAB_POLICY_INBOUND_THRESHOLD}")"
baseline_policy_id="$(ensure_policy "${LAB_POLICY_NAME}" "${baseline_body}")"

LAB_PL2_POLICY_NAME="$(env_value LAB_PL2_POLICY_NAME 'Lab PL2')"
LAB_PL2_POLICY_PARANOIA="$(env_value LAB_PL2_POLICY_PARANOIA 2)"
LAB_PL2_POLICY_INBOUND_THRESHOLD="$(env_value LAB_PL2_POLICY_INBOUND_THRESHOLD 3)"

pl2_body="$(printf '{"name":%s,"description":"Lab evaluation high-paranoia — PL%s anomaly threshold %s block","paranoia_level":%s,"inbound_anomaly_threshold":%s,"enforcement_mode":"block"}' \
  "$(json_string "${LAB_PL2_POLICY_NAME}")" "${LAB_PL2_POLICY_PARANOIA}" "${LAB_PL2_POLICY_INBOUND_THRESHOLD}" \
  "${LAB_PL2_POLICY_PARANOIA}" "${LAB_PL2_POLICY_INBOUND_THRESHOLD}")"
pl2_policy_id="$(ensure_policy "${LAB_PL2_POLICY_NAME}" "${pl2_body}")"

# ── Vhosts ─────────────────────────────────────────────────────────────────

LAB_JUICESHOP_DOMAIN="$(env_value LAB_JUICESHOP_DOMAIN juice.local)"
LAB_JUICESHOP_BACKEND_URL="$(env_value LAB_JUICESHOP_BACKEND_URL http://juiceshop:3000)"
LAB_FTW_DOMAIN="$(env_value LAB_FTW_DOMAIN ftw.local)"
LAB_FTW_BACKEND_URL="$(env_value LAB_FTW_BACKEND_URL http://ftw-backend:8080)"
LAB_DVWA_DOMAIN="$(env_value LAB_DVWA_DOMAIN dvwa.local)"
LAB_DVWA_BACKEND_URL="$(env_value LAB_DVWA_BACKEND_URL http://dvwa:80)"
LAB_WP_DOMAIN="$(env_value LAB_WP_DOMAIN wp.local)"
LAB_WP_BACKEND_URL="$(env_value LAB_WP_BACKEND_URL http://wordpress:80)"

echo "Registering lab vhosts (${LAB_JUICESHOP_DOMAIN}, ${LAB_FTW_DOMAIN}, ${LAB_DVWA_DOMAIN}, ${LAB_WP_DOMAIN})..."
ensure_vhost "${LAB_JUICESHOP_DOMAIN}" "${LAB_JUICESHOP_BACKEND_URL}" "OWASP Juice Shop — intentionally vulnerable app" "${baseline_policy_id}"
ensure_vhost "${LAB_FTW_DOMAIN}" "${LAB_FTW_BACKEND_URL}" "Albedo — CRS go-ftw regression backend" "${baseline_policy_id}"
ensure_vhost "${LAB_DVWA_DOMAIN}" "${LAB_DVWA_BACKEND_URL}" "DVWA — Damn Vulnerable Web Application" "${baseline_policy_id}"
ensure_vhost "${LAB_WP_DOMAIN}" "${LAB_WP_BACKEND_URL}" "WordPress — real CMS for FP measurement (no CRS exclusions)" "${baseline_policy_id}"

echo "Applying generated HAProxy/Coraza config..."
api_json POST /config/apply "${token}" >/dev/null

# ── DVWA DB initialisation (idempotent) ────────────────────────────────────
echo "Initialising DVWA database..."
curl -sf --max-time 30 \
  -c /tmp/dvwa-cookies.txt \
  -b /tmp/dvwa-cookies.txt \
  -d "create_db=Create+%2F+Reset+Database" \
  "http://127.0.0.1:${HAPROXY_HTTP_PORT}/setup.php" \
  -H "Host: ${LAB_DVWA_DOMAIN}" >/dev/null || echo "DVWA setup.php returned non-200 (may already be initialised)"

echo
echo "Eval lab ready: ${LAB_JUICESHOP_DOMAIN}, ${LAB_FTW_DOMAIN}, ${LAB_DVWA_DOMAIN}, ${LAB_WP_DOMAIN} via ${WAF_BASE_URL} (curl -H 'Host: <domain>')."
echo "Smoke (expect 403): curl -si -H 'Host: ${LAB_JUICESHOP_DOMAIN}' '${WAF_BASE_URL}/?q=1+UNION+SELECT+1--' | grep 'HTTP/'"
