#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"
ENV_FILE="${SCRIPT_DIR}/.env"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-180}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Copy deploy/demo/.env.example to deploy/demo/.env first." >&2
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

env_value() {
  local name="$1"
  local fallback="${2:-}"
  local value

  value="$(grep -E "^${name}=" "${ENV_FILE}" | tail -n 1 | cut -d= -f2- || true)"
  if [[ -z "${value}" ]]; then
    printf '%s' "${fallback}"
  else
    printf '%s' "${value}"
  fi
}

json_string() {
  python3 -c 'import json, sys; print(json.dumps(sys.argv[1]))' "$1"
}

api_json() {
  local method="$1"
  local path="$2"
  local token="${3:-}"
  local body="${4:-}"
  local response_file

  response_file="$(mktemp)"
  if [[ -n "${body}" ]]; then
    http_code="$(
      curl \
        --silent \
        --show-error \
        --output "${response_file}" \
        --write-out '%{http_code}' \
        --request "${method}" \
        --header "Content-Type: application/json" \
        ${token:+--header "Authorization: Bearer ${token}"} \
        --data "${body}" \
        "${API_BASE_URL}${path}"
    )"
  else
    http_code="$(
      curl \
        --silent \
        --show-error \
        --output "${response_file}" \
        --write-out '%{http_code}' \
        --request "${method}" \
        ${token:+--header "Authorization: Bearer ${token}"} \
        "${API_BASE_URL}${path}"
    )"
  fi

  if [[ "${http_code}" -lt 200 || "${http_code}" -ge 300 ]]; then
    echo "API ${method} ${path} failed with HTTP ${http_code}:" >&2
    cat "${response_file}" >&2
    rm -f "${response_file}"
    return 1
  fi

  cat "${response_file}"
  rm -f "${response_file}"
}

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

  echo "Waiting for ${service}..."
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

ensure_crs_bundle() {
  if compgen -G "${REPO_ROOT}/configs/coraza/crs/rules/*.conf" >/dev/null; then
    return
  fi

  echo "Missing OWASP CRS rules in configs/coraza/crs." >&2
  echo "Run: git submodule update --init --recursive" >&2
  echo "Then rerun: ./deploy/demo/setup-demo.sh" >&2
  exit 1
}

ADMIN_EMAIL="$(env_value ADMIN_EMAIL admin@example.com)"
ADMIN_PASSWORD="$(env_value ADMIN_PASSWORD GuardProxyDemo12345)"
ADMIN_FULL_NAME="$(env_value ADMIN_FULL_NAME 'Demo Administrator')"
DEMO_DOMAIN="$(env_value DEMO_DOMAIN app.local)"
DEMO_BACKEND_URL="$(env_value DEMO_BACKEND_URL http://demo-app:8080)"
DEMO_SECOND_DOMAIN="$(env_value DEMO_SECOND_DOMAIN api.local)"
DEMO_SECOND_BACKEND_URL="$(env_value DEMO_SECOND_BACKEND_URL http://demo-api:8080)"
HAPROXY_HTTP_PORT="$(env_value HAPROXY_HTTP_PORT 8080)"
HAPROXY_HTTPS_PORT="$(env_value HAPROXY_HTTPS_PORT 8443)"
BACKEND_HTTP_PORT="$(env_value BACKEND_HTTP_PORT 8000)"
FRONTEND_HTTP_PORT="$(env_value FRONTEND_HTTP_PORT 3000)"
API_BASE_URL="http://127.0.0.1:${BACKEND_HTTP_PORT}"
WAF_BASE_URL="http://127.0.0.1:${HAPROXY_HTTP_PORT}"
WAF_TLS_BASE_URL="https://127.0.0.1:${HAPROXY_HTTPS_PORT}"
FRONTEND_BASE_URL="http://localhost:${FRONTEND_HTTP_PORT}"

cd "${REPO_ROOT}"

ensure_crs_bundle

ensure_demo_certificate() {
  local cert_dir="${SCRIPT_DIR}/certs"
  local cert_file="${cert_dir}/demo.pem"
  local crt_file="${cert_dir}/demo.crt"
  local key_file="${cert_dir}/demo.key"

  if [[ -f "${cert_file}" ]]; then
    return
  fi

  if ! command -v openssl >/dev/null 2>&1; then
    echo "OpenSSL is required to generate the demo TLS certificate." >&2
    exit 1
  fi

  echo "Generating self-signed demo TLS certificate for ${DEMO_DOMAIN} and ${DEMO_SECOND_DOMAIN}..."
  mkdir -p "${cert_dir}"
  openssl req \
    -x509 \
    -nodes \
    -newkey rsa:2048 \
    -days 30 \
    -subj "/CN=${DEMO_DOMAIN}" \
    -addext "subjectAltName=DNS:${DEMO_DOMAIN},DNS:${DEMO_SECOND_DOMAIN}" \
    -keyout "${key_file}" \
    -out "${crt_file}" \
    >/dev/null 2>&1
  cat "${crt_file}" "${key_file}" > "${cert_file}"
}

enable_demo_https() {
  echo "Applying temporary demo HTTPS bind to generated HAProxy config..."
  "${COMPOSE[@]}" exec -T haproxy sh -c \
    "grep -q 'bind \\*:443 ssl crt /etc/haproxy/certs/demo.pem' /etc/haproxy/generated/current/haproxy.cfg || sed -i '/^[[:space:]]*bind \\*:80$/a\\    bind *:443 ssl crt /etc/haproxy/certs/demo.pem' /etc/haproxy/generated/current/haproxy.cfg"
  "${COMPOSE[@]}" exec -T haproxy haproxy -c -f /etc/haproxy/generated/current/haproxy.cfg >/dev/null
  "${COMPOSE[@]}" restart haproxy >/dev/null
  wait_for_healthy haproxy
}

ensure_demo_certificate
"${COMPOSE[@]}" up -d --build

wait_for_healthy backend
wait_for_healthy demo-app
wait_for_healthy demo-api
wait_for_healthy coraza
wait_for_healthy haproxy

echo "Seeding admin user..."
"${COMPOSE[@]}" exec -T backend /app/.venv/bin/python scripts/seed_admin.py \
  --email "${ADMIN_EMAIL}" \
  --password "${ADMIN_PASSWORD}" \
  --full-name "${ADMIN_FULL_NAME}"

echo "Logging in..."
login_body="$(
  printf '{"email":%s,"password":%s}' \
    "$(json_string "${ADMIN_EMAIL}")" \
    "$(json_string "${ADMIN_PASSWORD}")"
)"
token="$(
  api_json POST /auth/login "" "${login_body}" \
    | python3 -c 'import json, sys; print(json.load(sys.stdin)["access_token"])'
)"

echo "Ensuring demo WAF policy exists..."
policy_body='{"name":"Demo CRS","description":"Demo policy for app.local and api.local","paranoia_level":1,"inbound_anomaly_threshold":5,"outbound_anomaly_threshold":4,"enforcement_mode":"block"}'
policy_response="$(api_json POST /policies "${token}" "${policy_body}" || true)"
if [[ -z "${policy_response}" ]]; then
  policy_response="$(api_json GET /policies "${token}")"
fi
policy_id="$(
  POLICY_RESPONSE="${policy_response}" python3 - <<'PY'
import json
import os

data = json.loads(os.environ["POLICY_RESPONSE"])
if isinstance(data, list):
    for item in data:
        if item["name"] == "Demo CRS":
            print(item["id"])
            break
    else:
        raise SystemExit("Demo CRS policy not found")
else:
    print(data["id"])
PY
)"

ensure_vhost() {
  local domain="$1"
  local backend_url="$2"
  local description="$3"
  local vhost_body
  local vhost_response
  local vhosts_response
  local vhost_id

  echo "Ensuring vhost ${domain} -> ${backend_url} exists..."
  vhost_body="$(
    printf '{"domain":%s,"backend_url":%s,"description":%s,"ssl_enabled":false,"is_active":true,"policy_id":%s}' \
      "$(json_string "${domain}")" \
      "$(json_string "${backend_url}")" \
      "$(json_string "${description}")" \
      "${policy_id}"
  )"
  vhost_response="$(api_json POST /vhosts "${token}" "${vhost_body}" || true)"
  if [[ -n "${vhost_response}" ]]; then
    return
  fi

  vhosts_response="$(api_json GET /vhosts "${token}")"
  vhost_id="$(
    VHOSTS_RESPONSE="${vhosts_response}" DEMO_DOMAIN="${domain}" python3 - <<'PY'
import json
import os

data = json.loads(os.environ["VHOSTS_RESPONSE"])
domain = os.environ["DEMO_DOMAIN"]
for item in data:
    if item["domain"] == domain:
        print(item["id"])
        break
else:
    raise SystemExit(f"vhost {domain!r} not found")
PY
    )"
  vhost_response="$(api_json PATCH "/vhosts/${vhost_id}" "${token}" "${vhost_body}")"
}

ensure_vhost "${DEMO_DOMAIN}" "${DEMO_BACKEND_URL}" "Demo frontend application"
ensure_vhost "${DEMO_SECOND_DOMAIN}" "${DEMO_SECOND_BACKEND_URL}" "Demo API application"

echo "Applying generated HAProxy/Coraza config..."
api_json POST /config/apply "${token}" >/dev/null
enable_demo_https

echo
echo "Demo is ready."
echo "Admin panel: ${FRONTEND_BASE_URL}"
echo "Backend API:  ${API_BASE_URL}"
echo "WAF proxy:    ${WAF_BASE_URL}"
echo "WAF TLS:      ${WAF_TLS_BASE_URL}"
echo
echo "Try:"
echo "  curl -i -H 'Host: ${DEMO_DOMAIN}' '${WAF_BASE_URL}/hello?name=demo'"
echo "  curl -i -H 'Host: ${DEMO_SECOND_DOMAIN}' '${WAF_BASE_URL}/v1/status'"
echo "  curl -k -i -H 'Host: ${DEMO_DOMAIN}' '${WAF_TLS_BASE_URL}/hello?tls=1'"
echo "  curl -k -i -H 'Host: ${DEMO_SECOND_DOMAIN}' '${WAF_TLS_BASE_URL}/v1/status'"
