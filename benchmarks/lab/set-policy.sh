#!/usr/bin/env bash
# set-policy.sh — Switch all lab vhosts to the PL1 or PL2 policy and reload config.
#
# setup-lab.sh creates both the "Lab Baseline" (PL1) and "Lab PL2" policies and binds
# all lab vhosts to PL1 by default. This script re-points the vhosts to the requested
# policy and applies the generated HAProxy/Coraza config, so a PL2 sweep can run
# against the same lab targets without re-running setup-lab.sh.
#
# Prerequisites:
#   - benchmarks/lab/.env (copy from benchmarks/lab/.env.example)
#   - Lab already brought up via `make lab-up` (setup-lab.sh has already created
#     the "Lab Baseline" and "Lab PL2" policies and the four lab vhosts)
#
# Usage:
#   POLICY=pl1 bash benchmarks/lab/set-policy.sh
#   POLICY=pl2 bash benchmarks/lab/set-policy.sh

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
CORE_ENV="${REPO_ROOT}/deploy/docker/.env"
LAB_ENV="${SCRIPT_DIR}/.env"
POLICY="${POLICY:-pl1}"

for f in "${CORE_ENV}" "${LAB_ENV}"; do
  if [[ ! -f "${f}" ]]; then
    echo "Missing ${f}. Copy the matching .env.example first." >&2
    exit 1
  fi
done

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

# ── Resolve target policy ────────────────────────────────────────────────────

case "${POLICY}" in
  pl1)
    TARGET_POLICY_NAME="$(env_value LAB_POLICY_NAME 'Lab Baseline')"
    ;;
  pl2)
    TARGET_POLICY_NAME="$(env_value LAB_PL2_POLICY_NAME 'Lab PL2')"
    ;;
  *)
    echo "Unknown POLICY '${POLICY}' (expected pl1 or pl2)." >&2
    exit 1
    ;;
esac

ADMIN_EMAIL="$(env_value ADMIN_EMAIL admin@example.com)"
ADMIN_PASSWORD="$(env_value ADMIN_PASSWORD GuardProxyDemo12345)"
BACKEND_HTTP_PORT="$(env_value BACKEND_HTTP_PORT 8000)"
API_BASE_URL="http://127.0.0.1:${BACKEND_HTTP_PORT}"

LAB_JUICESHOP_DOMAIN="$(env_value LAB_JUICESHOP_DOMAIN juice.local)"
LAB_FTW_DOMAIN="$(env_value LAB_FTW_DOMAIN ftw.local)"
LAB_DVWA_DOMAIN="$(env_value LAB_DVWA_DOMAIN dvwa.local)"
LAB_WP_DOMAIN="$(env_value LAB_WP_DOMAIN wp.local)"

# ── Main ───────────────────────────────────────────────────────────────────

echo "Logging in..."
login_body="$(printf '{"email":%s,"password":%s}' "$(json_string "${ADMIN_EMAIL}")" "$(json_string "${ADMIN_PASSWORD}")")"
token="$(api_json POST /auth/login "" "${login_body}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"

echo "Looking up policy '${TARGET_POLICY_NAME}'..."
policies_response="$(api_json GET /policies "${token}")"
policy_lookup="$(POLICIES="${policies_response}" POLICY_NAME="${TARGET_POLICY_NAME}" python3 - <<'PY'
import json, os, sys
data = json.loads(os.environ["POLICIES"])
name = os.environ["POLICY_NAME"]
items = data if isinstance(data, list) else [data]
for item in items:
    if item["name"] == name:
        print(item["id"], item.get("paranoia_level", "?"))
        sys.exit(0)
sys.exit(f"Policy '{name}' not found. Run `make lab-up` (setup-lab.sh) first.")
PY
)"
read -r policy_id policy_paranoia <<<"${policy_lookup}"

echo "Fetching vhosts..."
vhosts_response="$(api_json GET /vhosts "${token}")"

set_vhost_policy() {
  local domain="$1"
  local vhost_id
  vhost_id="$(VHOSTS="${vhosts_response}" DOMAIN="${domain}" python3 - <<'PY'
import json, os, sys
data = json.loads(os.environ["VHOSTS"]); domain = os.environ["DOMAIN"]
for item in data:
    if item["domain"] == domain:
        print(item["id"]); sys.exit(0)
sys.exit(f"vhost {domain!r} not found. Run `make lab-up` (setup-lab.sh) first.")
PY
  )"
  echo "  ${domain} -> policy_id=${policy_id}"
  api_json PATCH "/vhosts/${vhost_id}" "${token}" "{\"policy_id\":${policy_id}}" >/dev/null
}

echo "Switching lab vhosts to '${TARGET_POLICY_NAME}' (paranoia ${policy_paranoia})..."
set_vhost_policy "${LAB_JUICESHOP_DOMAIN}"
set_vhost_policy "${LAB_FTW_DOMAIN}"
set_vhost_policy "${LAB_DVWA_DOMAIN}"
set_vhost_policy "${LAB_WP_DOMAIN}"

echo "Applying generated HAProxy/Coraza config..."
api_json POST /config/apply "${token}" >/dev/null

echo
echo "Active policy: ${TARGET_POLICY_NAME} (paranoia ${policy_paranoia})"
