#!/usr/bin/env bash
# lib.sh — Shared helpers for eval lab runner scripts.
#
# Source this file at the top of each runner:
#   source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
#
# Provides: REPO_ROOT, RESULTS_DIR, RUN_DIR, manifest helpers, docker network name.

: "${RUN_ID:?RUN_ID must be set before sourcing lib.sh}"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../../.." && pwd)"
LAB_DIR="${REPO_ROOT}/benchmarks/lab"
RESULTS_BASE="${REPO_ROOT}/benchmarks/results"
RUN_DIR="${RESULTS_BASE}/run-${RUN_ID}"
CORE_ENV="${REPO_ROOT}/docker/.env"
LAB_ENV="${LAB_DIR}/.env"

# Docker network shared by the real stack and lab targets.
# Compose derives the network name from the project name (directory name by
# default). Override via COMPOSE_PROJECT_NAME when running the lab alongside
# another guard-proxy deployment on the same host.
DOCKER_NETWORK="${COMPOSE_PROJECT_NAME:-guard-proxy}_gp_internal"

# ── Environment helpers ────────────────────────────────────────────────────

env_value() {
  local name="$1"; local fallback="${2:-}"; local value
  value="$(grep -E "^${name}=" "${CORE_ENV}" "${LAB_ENV}" 2>/dev/null | tail -n 1 | cut -d= -f2- || true)"
  if [[ -z "${value}" ]]; then printf '%s' "${fallback}"; else printf '%s' "${value}"; fi
}

HAPROXY_HTTP_PORT="$(env_value HAPROXY_HTTP_PORT 8080)"
BACKEND_HTTP_PORT="$(env_value BACKEND_HTTP_PORT 8000)"
LAB_JUICESHOP_DOMAIN="$(env_value LAB_JUICESHOP_DOMAIN juice.local)"
LAB_DVWA_DOMAIN="$(env_value LAB_DVWA_DOMAIN dvwa.local)"
LAB_WP_DOMAIN="$(env_value LAB_WP_DOMAIN wp.local)"
LAB_FTW_DOMAIN="$(env_value LAB_FTW_DOMAIN ftw.local)"
ATTACKER_CPUSET="$(env_value LAB_ATTACKER_CPUSET '')"

# ── Policy selection ───────────────────────────────────────────────────────

# shellcheck source=benchmarks/lab/policy-profiles.sh
source "${LAB_DIR}/policy-profiles.sh"

# Record the policy that actually protects TARGET_VHOST, read from the backend
# API: every lab vhost has its own policy, so the profile name in POLICY
# (pl1|pl2, which only labels the results directory) does not say which
# settings a given vhost runs with. Sets POLICY_JSON for write_summary and
# warns when the vhost's settings do not match the POLICY profile.
resolve_policy() {
  : "${TARGET_VHOST:?TARGET_VHOST must be set before resolve_policy}"
  load_policy_profile "${POLICY:-pl1}"
  POLICY_JSON="$(
    API_BASE_URL="http://127.0.0.1:${BACKEND_HTTP_PORT}" \
    ADMIN_EMAIL="$(env_value ADMIN_EMAIL admin@example.com)" \
    ADMIN_PASSWORD="$(env_value ADMIN_PASSWORD GuardProxyDemo12345)" \
    DOMAIN="${TARGET_VHOST}" \
    PROFILE="${POLICY:-pl1}" \
    PROFILE_PARANOIA="${PROFILE_PARANOIA}" \
    PROFILE_INBOUND_THRESHOLD="${PROFILE_INBOUND_THRESHOLD}" \
    python3 - <<'PY'
import json, os, sys, time, urllib.error, urllib.request

base = os.environ["API_BASE_URL"]

def call(path, token=None, body=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(base + path, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)

credentials = {"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]}
# /auth/login allows 5 requests per minute per IP and a sweep logs in once per
# runner; wait out the limit instead of failing a long evaluation run.
for attempt in range(3):
    try:
        token = call("/auth/login", body=credentials)["access_token"]
        break
    except urllib.error.HTTPError as error:
        if error.code != 429 or attempt == 2:
            raise
        wait = int(error.headers.get("Retry-After", "60"))
        print(f"Login rate-limited; retrying in {wait}s.", file=sys.stderr)
        time.sleep(wait)
domain = os.environ["DOMAIN"]
vhost = next(
    (v for v in call("/vhosts?per_page=500", token)["items"] if v["domain"] == domain),
    None,
)
if vhost is None:
    sys.exit(f"vhost {domain!r} not found. Run `make lab-up` first.")
policy = call(f"/vhosts/{vhost['id']}", token).get("policy")
if policy is None:
    sys.exit(f"vhost {domain!r} has no policy. Run `make lab-up` first.")
if (policy["paranoia_level"], policy["inbound_anomaly_threshold"]) != (
    int(os.environ["PROFILE_PARANOIA"]),
    int(os.environ["PROFILE_INBOUND_THRESHOLD"]),
):
    print(
        f"WARNING: {domain} runs policy {policy['name']!r} at PL{policy['paranoia_level']}"
        f" / threshold {policy['inbound_anomaly_threshold']}, not the"
        f" {os.environ['PROFILE']} profile. Run `make set-policy POLICY=...` first"
        " if that is not intended.",
        file=sys.stderr,
    )
print(json.dumps({
    "name": policy["name"],
    "paranoia": policy["paranoia_level"],
    "inbound_threshold": policy["inbound_anomaly_threshold"],
    "outbound_threshold": policy["outbound_anomaly_threshold"],
    "mode": policy["enforcement_mode"],
}))
PY
  )"
  echo "Target ${TARGET_VHOST} is protected by: ${POLICY_JSON}"
}

# ── Directory setup ────────────────────────────────────────────────────────

setup_run_dir() {
  local scenario="$1"
  local dir="${RUN_DIR}/${scenario}"
  mkdir -p "${dir}"
  printf '%s' "${dir}"
}

# ── Manifest ───────────────────────────────────────────────────────────────

write_manifest() {
  local manifest="${RUN_DIR}/manifest.json"
  if [[ -f "${manifest}" ]]; then return; fi  # written once per run

  local git_sha; git_sha="$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo "unknown")"
  local host_cpu; host_cpu="$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo "unknown")"
  local host_mem_gb; host_mem_gb="$(awk '/^MemTotal:/{printf "%.0f", $2/1024/1024}' /proc/meminfo 2>/dev/null || echo "unknown")"
  local host_load; host_load="$(cut -d' ' -f1-3 /proc/loadavg 2>/dev/null || uptime | awk -F'load averages:' '{print $2}' | xargs || echo "unknown")"
  local timestamp; timestamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

  python3 - <<PY
import json, os
manifest = {
    "run_id": "${RUN_ID}",
    "timestamp": "${timestamp}",
    "git_sha": "${git_sha}",
    "host": {
        "cpu_cores": "${host_cpu}",
        "mem_gb": "${host_mem_gb}",
        "load_avg_at_start": "${host_load}",
        "noisy_neighbor": True  # shared Proxmox homelab — see evaluation-plan.md §9
    },
    "config": {
        "haproxy_http_port": int("${HAPROXY_HTTP_PORT}"),
        "lab_env": "${LAB_ENV}",
        "vhosts": {
            "juiceshop": "${LAB_JUICESHOP_DOMAIN}",
            "ftw": "${LAB_FTW_DOMAIN}",
            "dvwa": "${LAB_DVWA_DOMAIN}",
            "wordpress": "${LAB_WP_DOMAIN}"
        }
    }
}
with open("${manifest}", "w") as f:
    json.dump(manifest, f, indent=2)
print("Manifest written to ${manifest}")
PY
}

# ── Docker helpers ─────────────────────────────────────────────────────────

# Get the container ID for a compose service.
compose_container_id() {
  local service="$1"
  docker compose \
    -f "${REPO_ROOT}/docker/docker-compose.yml" \
    -f "${LAB_DIR}/docker-compose.targets.yml" \
    --env-file "${CORE_ENV}" \
    --env-file "${LAB_ENV}" \
    ps -q "${service}" 2>/dev/null || true
}

# Sample peak memory + avg CPU for a container over a duration.
# Writes to a file and prints the final JSON snippet.
sample_container_resources() {
  local container_name="$1"  # docker service name
  local duration_s="${2:-60}"
  local out_file="$3"
  local interval=2
  local samples=0
  local cpu_sum=0
  local mem_peak=0

  local end_time=$(( SECONDS + duration_s ))
  while (( SECONDS < end_time )); do
    local stats
    stats="$(docker stats --no-stream --format '{{.CPUPerc}}\t{{.MemUsage}}' "${container_name}" 2>/dev/null || true)"
    if [[ -n "${stats}" ]]; then
      local cpu_pct mem_mb
      cpu_pct="$(awk -F'\t' '{gsub(/%/,"",$1); print $1}' <<< "${stats}")"
      mem_mb="$(awk -F'\t' '{split($2,a,/[A-Za-z]/); print a[1]+0}' <<< "${stats}")"
      cpu_sum="$(python3 -c "print(${cpu_sum} + ${cpu_pct:-0})")"
      if python3 -c "exit(0 if ${mem_mb:-0} > ${mem_peak} else 1)" 2>/dev/null; then
        mem_peak="${mem_mb:-0}"
      fi
      samples=$(( samples + 1 ))
    fi
    sleep "${interval}"
  done

  local cpu_avg=0
  if (( samples > 0 )); then
    cpu_avg="$(python3 -c "print(round(${cpu_sum} / ${samples}, 2))")"
  fi

  python3 - <<PY > "${out_file}"
import json
print(json.dumps({"mem_mb_peak": ${mem_peak}, "cpu_pct_avg": ${cpu_avg}, "samples": ${samples}}))
PY
}

copy_audit_log_snapshot() {
  local out_dir="$1"
  local out_file="${2:-${out_dir}/coraza-audit.log}"
  local coraza_id
  # Compose lookup, not a name filter: on a shared host "coraza" also
  # matches other guard-proxy deployments' containers.
  coraza_id="$(compose_container_id coraza)"
  if [[ -z "${coraza_id}" ]]; then
    echo "Note: coraza container not found; audit snapshot skipped." >&2
    return 0
  fi
  docker cp "${coraza_id}:/var/log/coraza/audit.log" "${out_file}" 2>/dev/null || {
    echo "Note: could not copy Coraza audit log to ${out_file}." >&2
    return 0
  }
}

# ── Output helpers ─────────────────────────────────────────────────────────

# Requires resolve_policy to have run (POLICY_JSON).
write_summary() {
  local scenario="$1"
  local target_vhost="$2"
  local detection_json="$3"      # {"true_positive":...,"false_negative":...,"tpr":...,"fpr":...}
  local performance_json="$4"    # {"rps":...,"latency_ms":...} or {}
  local resources_json="${5:-}"
  if [[ -z "${resources_json}" ]]; then resources_json='{}'; fi

  RUN_ID="${RUN_ID}" RUN_DIR="${RUN_DIR}" SCENARIO="${scenario}" \
  TARGET_VHOST="${target_vhost}" POLICY_JSON="${POLICY_JSON:?resolve_policy must run first}" \
  DETECTION_JSON="${detection_json}" PERFORMANCE_JSON="${performance_json}" \
  RESOURCES_JSON="${resources_json}" python3 - <<'PY'
import json, os

detection = json.loads(os.environ["DETECTION_JSON"])
performance = json.loads(os.environ["PERFORMANCE_JSON"])
resources = json.loads(os.environ["RESOURCES_JSON"])
policy = json.loads(os.environ["POLICY_JSON"])
summary = {
    "run_id": os.environ["RUN_ID"],
    "scenario": os.environ["SCENARIO"],
    "target_vhost": os.environ["TARGET_VHOST"],
    "policy": policy,
    "detection": detection,
    "performance": performance,
    "resources": resources,
}

out = os.path.join(os.environ["RUN_DIR"], os.environ["SCENARIO"], "summary.json")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w") as f:
    json.dump(summary, f, indent=2)
print(f"Summary written to {out}")
PY
}
