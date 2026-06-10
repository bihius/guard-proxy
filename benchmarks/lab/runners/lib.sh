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
CORE_ENV="${REPO_ROOT}/deploy/docker/.env"
LAB_ENV="${LAB_DIR}/.env"

# Docker network shared by the real stack and lab targets.
DOCKER_NETWORK="guard-proxy_gp_internal"

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

# ── Policy selection ───────────────────────────────────────────────────────

# Resolve the active policy for this run based on POLICY (pl1|pl2, default pl1).
# Exports POLICY_NAME and POLICY_PARANOIA from the matching LAB_POLICY_* /
# LAB_PL2_POLICY_* env vars.
resolve_policy() {
  local policy="${POLICY:-pl1}"
  case "${policy}" in
    pl1)
      POLICY_NAME="$(env_value LAB_POLICY_NAME 'Lab Baseline')"
      POLICY_PARANOIA="$(env_value LAB_POLICY_PARANOIA 1)"
      ;;
    pl2)
      POLICY_NAME="$(env_value LAB_PL2_POLICY_NAME 'Lab PL2')"
      POLICY_PARANOIA="$(env_value LAB_PL2_POLICY_PARANOIA 2)"
      ;;
    *)
      echo "Unknown POLICY '${policy}' (expected pl1 or pl2)." >&2
      exit 1
      ;;
  esac
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
    -f "${REPO_ROOT}/deploy/docker/docker-compose.yml" \
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
  coraza_id="$(docker ps --filter "name=coraza" --format "{{.ID}}" | head -1 || true)"
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

write_summary() {
  local scenario="$1"
  local target_vhost="$2"
  local policy_name="$3"
  local detection_json="$4"      # {"true_positive":...,"false_negative":...,"tpr":...,"fpr":...}
  local performance_json="$5"    # {"rps":...,"latency_ms":...} or {}
  local resources_json="${6:-}"
  if [[ -z "${resources_json}" ]]; then resources_json='{}'; fi
  local policy_paranoia="${7:-}"

  RUN_ID="${RUN_ID}" RUN_DIR="${RUN_DIR}" SCENARIO="${scenario}" \
  TARGET_VHOST="${target_vhost}" POLICY_NAME="${policy_name}" \
  DETECTION_JSON="${detection_json}" PERFORMANCE_JSON="${performance_json}" \
  RESOURCES_JSON="${resources_json}" POLICY_PARANOIA="${policy_paranoia}" python3 - <<'PY'
import json, os

detection = json.loads(os.environ["DETECTION_JSON"])
performance = json.loads(os.environ["PERFORMANCE_JSON"])
resources = json.loads(os.environ["RESOURCES_JSON"])

policy = {"name": os.environ["POLICY_NAME"]}
paranoia_raw = os.environ.get("POLICY_PARANOIA", "")
if paranoia_raw != "":
    try:
        policy["paranoia"] = int(paranoia_raw)
    except ValueError:
        policy["paranoia"] = paranoia_raw

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
