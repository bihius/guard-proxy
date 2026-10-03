#!/usr/bin/env bash
# set-policy.sh — Put lab vhosts on the PL1 or PL2 profile and reload config.
#
# Every lab vhost has its own policy ("Lab <domain>", created by setup-lab.sh).
# This script writes the requested profile's paranoia level and anomaly
# thresholds into the policy of each selected vhost and applies the generated
# HAProxy/Coraza config. Other vhosts and each policy's own tuning (rule
# overrides, exclusions, custom rules) are left untouched.
#
# Prerequisites:
#   - benchmarks/lab/.env (copy from benchmarks/lab/.env.example)
#   - Lab already brought up via `make lab-up`
#
# Usage:
#   POLICY=pl1 bash benchmarks/lab/set-policy.sh                        # all lab vhosts
#   POLICY=pl2 TARGET_VHOST=wp.local bash benchmarks/lab/set-policy.sh  # one vhost

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
CORE_ENV="${REPO_ROOT}/docker/.env"
LAB_ENV="${SCRIPT_DIR}/.env"
POLICY="${POLICY:-pl1}"
TARGET_VHOST="${TARGET_VHOST:-}"

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

# shellcheck source=benchmarks/lab/policy-profiles.sh
source "${SCRIPT_DIR}/policy-profiles.sh"
load_policy_profile "${POLICY}"

ADMIN_EMAIL="$(env_value ADMIN_EMAIL admin@example.com)"
ADMIN_PASSWORD="$(env_value ADMIN_PASSWORD GuardProxyDemo12345)"
BACKEND_HTTP_PORT="$(env_value BACKEND_HTTP_PORT 8000)"
API_BASE_URL="http://127.0.0.1:${BACKEND_HTTP_PORT}"

if [[ -n "${TARGET_VHOST}" ]]; then
  DOMAINS=("${TARGET_VHOST}")
else
  DOMAINS=(
    "$(env_value LAB_FTW_DOMAIN ftw.local)"
    "$(env_value LAB_WP_DOMAIN wp.local)"
  )
fi

# ── Main ───────────────────────────────────────────────────────────────────

# /auth/login allows 5 requests per minute per IP; eval-sweep logs in from
# every runner, so wait out the limit instead of aborting the sweep.
login() {
  local body response_file http_code attempt
  body="$(printf '{"email":%s,"password":%s}' "$(json_string "${ADMIN_EMAIL}")" "$(json_string "${ADMIN_PASSWORD}")")"
  response_file="$(mktemp)"
  for attempt in 1 2 3; do
    http_code="$(curl --silent --show-error --output "${response_file}" --write-out '%{http_code}' \
      --request POST --header "Content-Type: application/json" --data "${body}" "${API_BASE_URL}/auth/login")"
    if [[ "${http_code}" == 200 ]]; then
      python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])' <"${response_file}"
      rm -f "${response_file}"; return 0
    fi
    if [[ "${http_code}" != 429 || "${attempt}" == 3 ]]; then break; fi
    echo "Login rate-limited; retrying in 60s." >&2
    sleep 60
  done
  echo "API POST /auth/login failed with HTTP ${http_code}:" >&2
  cat "${response_file}" >&2; rm -f "${response_file}"; return 1
}

echo "Logging in..."
token="$(login)"
vhosts_response="$(api_json GET "/vhosts?per_page=500" "${token}")"
profile_body="$(printf '{"paranoia_level":%s,"inbound_anomaly_threshold":%s,"outbound_anomaly_threshold":%s,"enforcement_mode":"block","is_active":true}' \
  "${PROFILE_PARANOIA}" "${PROFILE_INBOUND_THRESHOLD}" "${PROFILE_OUTBOUND_THRESHOLD}")"

set_vhost_profile() {
  local domain="$1"
  local vhost_id detail policy_id
  vhost_id="$(VHOSTS="${vhosts_response}" DOMAIN="${domain}" python3 - <<'PY'
import json, os, sys
data = json.loads(os.environ["VHOSTS"]); domain = os.environ["DOMAIN"]
items = data["items"] if isinstance(data, dict) and "items" in data else data
for item in items:
    if item["domain"] == domain:
        print(item["id"]); sys.exit(0)
sys.exit(f"vhost {domain!r} not found. Run `make lab-up` (setup-lab.sh) first.")
PY
  )"
  detail="$(api_json GET "/vhosts/${vhost_id}" "${token}")"
  # Refuse to edit a policy that is not this vhost's own: changing a shared
  # policy would silently move other vhosts to the profile as well.
  policy_id="$(DETAIL="${detail}" EXPECTED="$(lab_policy_name "${domain}")" python3 - <<'PY'
import json, os, sys
policy = json.loads(os.environ["DETAIL"]).get("policy")
expected = os.environ["EXPECTED"]
if policy is None or policy["name"] != expected:
    found = "no policy" if policy is None else f"policy {policy['name']!r}"
    sys.exit(f"vhost uses {found}, expected its own {expected!r}. Run `make lab-up` (setup-lab.sh) first.")
print(policy["id"])
PY
  )"
  api_json PATCH "/policies/${policy_id}" "${token}" "${profile_body}" >/dev/null
  echo "  ${domain}: '$(lab_policy_name "${domain}")' -> PL${PROFILE_PARANOIA}, inbound threshold ${PROFILE_INBOUND_THRESHOLD}"
}

echo "Setting profile ${POLICY} on ${#DOMAINS[@]} lab vhost(s)..."
for domain in "${DOMAINS[@]}"; do
  set_vhost_profile "${domain}"
done

echo "Applying generated HAProxy/Coraza config..."
api_json POST /config/apply "${token}" >/dev/null

echo
echo "Profile ${POLICY} active on: ${DOMAINS[*]}"
