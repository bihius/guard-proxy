#!/usr/bin/env bash
# run-load.sh — Test 3: latency and RPS overhead (WAF vs direct).
#
# Albedo isolates HAProxy+Coraza cost; WordPress measures a real application's
# end-to-end behavior. Both paths use the same workload and target.
#
# Two ways to run wrk:
#   - local (default): wrk runs in a container on the lab's Docker network.
#     Load generator and WAF share the host's CPUs. For smoke runs.
#   - manual: set LOAD_CLIENT=manual and LAB_SERVER_ADDR in benchmarks/lab/.env. The script prints
#     the wrk command for each run; you start it by hand on the separate load
#     client and paste its output back here. The measured HTTP traffic goes
#     from the client to the server's HAProxy port (WAF) and the selected
#     target's baseline port (direct). Nothing connects to the client.
#
# Samples coraza + haproxy container resource usage during the WAF run.
#
# Output:
#   benchmarks/results/run-<RUN_ID>/load-<vhost>/waf.txt
#   benchmarks/results/run-<RUN_ID>/load-<vhost>/direct.txt
#   benchmarks/results/run-<RUN_ID>/load-<vhost>/resources-coraza.json
#   benchmarks/results/run-<RUN_ID>/load-<vhost>/resources-haproxy.json
#   benchmarks/results/run-<RUN_ID>/load-<vhost>/performance.json
#   benchmarks/results/run-<RUN_ID>/load-<vhost>/summary.json
#
# Usage:
#   RUN_ID=... bash benchmarks/lab/runners/run-load.sh
#   RUN_ID=... LOAD_CLIENT=manual bash benchmarks/lab/runners/run-load.sh
#
# Manual mode builds URLs from LAB_SERVER_ADDR and the selected target's
# baseline-only port (LAB_FTW_DIRECT_PORT or LAB_WP_DIRECT_PORT).

set -Eeuo pipefail
: "${RUN_ID:=$(date +%Y%m%d-%H%M%S)}"
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

LOAD_TARGET="${LOAD_TARGET:-albedo}"
case "${LOAD_TARGET}" in
  albedo)
    TARGET_VHOST="${TARGET_VHOST:-${LAB_FTW_DOMAIN}}"
    DIRECT_HOST="${DIRECT_HOST:-ftw-backend}"
    DIRECT_PORT="${DIRECT_PORT:-8080}"
    DIRECT_PUBLIC_PORT="$(env_value LAB_FTW_DIRECT_PORT 18080)"
    ;;
  wordpress)
    TARGET_VHOST="${TARGET_VHOST:-${LAB_WP_DOMAIN}}"
    DIRECT_HOST="wordpress"
    DIRECT_PORT=80
    DIRECT_PUBLIC_PORT="$(env_value LAB_WP_DIRECT_PORT 18081)"
    ;;
  *)
    echo "Unknown LOAD_TARGET '${LOAD_TARGET}' (expected albedo or wordpress)." >&2
    exit 1
    ;;
esac
resolve_policy
# elswork/wrk ships native amd64+arm64 builds of wrk 4.2.0 (williamyeh/wrk is
# amd64-only and segfaults under emulation on Apple Silicon). Pinned by digest
# so re-runs use the same binary; the digest is recorded in performance.json.
WRK_IMAGE="elswork/wrk:4.2.0@sha256:529f8fe35924e549cc270d4128406d5863043e756c31395afd08acccc74ada79"
LUA_SCRIPT="${REPO_ROOT}/benchmarks/lab/scenarios/load/benign-mix.lua"

THREADS="${LOAD_THREADS:-2}"
CONNECTIONS="${LOAD_CONNECTIONS:-20}"
DURATION="${LOAD_DURATION:-30s}"
WARMUP_DURATION=5s

LOAD_CLIENT="${LOAD_CLIENT:-local}"
LAB_SERVER_ADDR="$(env_value LAB_SERVER_ADDR 127.0.0.1)"

case "${LOAD_CLIENT}" in
  manual)
    LOAD_MODE="manual"
    if [[ "${LAB_SERVER_ADDR}" == 127.0.0.1 ]]; then
      echo "LOAD_CLIENT=manual needs LAB_SERVER_ADDR in benchmarks/lab/.env set to the address the client reaches; restart the lab (make lab-up) after changing it." >&2
      exit 1
    fi
    if [[ ! -t 0 ]]; then
      echo "LOAD_CLIENT=manual needs an interactive terminal to paste wrk output into." >&2
      exit 1
    fi
    WAF_URL="http://${LAB_SERVER_ADDR}:${HAPROXY_HTTP_PORT}/"
    DIRECT_URL="http://${LAB_SERVER_ADDR}:${DIRECT_PUBLIC_PORT}/"
    ;;
  local)
    LOAD_MODE="local"
    WAF_URL="http://haproxy:80/"
    DIRECT_URL="http://${DIRECT_HOST}:${DIRECT_PORT}/"
    ;;
  *)
    echo "Unknown LOAD_CLIENT '${LOAD_CLIENT}' (expected local or manual)." >&2
    exit 1
    ;;
esac

write_manifest
SCENARIO="load-${TARGET_VHOST}"
OUT_DIR="$(setup_run_dir "${SCENARIO}")"

if [[ "${LOAD_MODE}" == local ]]; then
  WRK_VERSION="$(docker run --rm "${WRK_IMAGE}" -v 2>&1 | head -n 1 || true)"
else
  WRK_VERSION=""  # wrk's run output does not include its version
fi

echo "=== Load test: WAF vs direct ==="
echo "Target vhost : ${TARGET_VHOST}"
echo "Load client  : ${LOAD_MODE}${WRK_VERSION:+, ${WRK_VERSION}}"
echo "WAF URL      : ${WAF_URL}"
echo "Direct URL   : ${DIRECT_URL}"
echo "Load         : ${THREADS} threads, ${CONNECTIONS} connections, ${DURATION}"
echo "Output dir   : ${OUT_DIR}"
echo ""

CORAZA_CONTAINER="$(compose_container_id coraza)"
HAPROXY_CONTAINER="$(compose_container_id haproxy)"

start_resource_sampling() {
  if [[ -n "${CORAZA_CONTAINER}" ]]; then
    sample_container_resources "${CORAZA_CONTAINER}" "${DURATION}" "${OUT_DIR}/resources-coraza.json" &
    SAMPLER_CORAZA_PID=$!
  fi
  if [[ -n "${HAPROXY_CONTAINER}" ]]; then
    sample_container_resources "${HAPROXY_CONTAINER}" "${DURATION}" "${OUT_DIR}/resources-haproxy.json" &
    SAMPLER_HAPROXY_PID=$!
  fi
}

# run_wrk <case_id> <url> <out_file> [sample] [duration] [scenario]
# Only measured runs start coraza/haproxy resource sampling.
run_wrk() {
  local case_id="$1" url="$2" out_file="$3" sample="${4:-}"
  local duration="${5:-${DURATION}}" scenario="${6:-${SCENARIO}}"
  if [[ "${LOAD_MODE}" == local ]]; then
    [[ -z "${sample}" ]] || start_resource_sampling
    docker run --rm --cpuset-cpus="${ATTACKER_CPUSET}" \
      --network "${DOCKER_NETWORK}" \
      -v "${LUA_SCRIPT}:/benign-mix.lua:ro" \
      -e "LOAD_TARGET=${LOAD_TARGET}" \
      -e "LOAD_VHOST=${TARGET_VHOST}" \
      -e "EVAL_RUN_ID=${RUN_ID}" \
      -e "EVAL_SCENARIO=${scenario}" \
      -e "EVAL_CASE=${case_id}" \
      "${WRK_IMAGE}" \
      -t "${THREADS}" -c "${CONNECTIONS}" -d "${duration}" \
      -s /benign-mix.lua \
      --latency \
      "${url}" \
      > "${out_file}" 2>&1
    return
  fi

  # `env VAR=value cmd` works in bash, zsh and fish alike.
  echo "On the load client, in a checkout of commit $(git -C "${REPO_ROOT}" rev-parse --short HEAD), run:"
  echo ""
  printf '  env LOAD_TARGET=%q LOAD_VHOST=%q EVAL_RUN_ID=%q EVAL_SCENARIO=%q EVAL_CASE=%q \\\n' \
    "${LOAD_TARGET}" "${TARGET_VHOST}" "${RUN_ID}" "${scenario}" "${case_id}"
  printf '    wrk -t %q -c %q -d %q -s benchmarks/lab/scenarios/load/benign-mix.lua --latency %q\n' \
    "${THREADS}" "${CONNECTIONS}" "${duration}" "${url}"
  echo ""
  if [[ "${case_id}" == warmup-* ]]; then
    read -r -p "Run this warm-up on the client; press Enter after it finishes. Do not paste its output... " _
    return
  fi
  read -r -p "Press Enter here at the same moment you start wrk on the client... " _
  [[ -z "${sample}" ]] || start_resource_sampling
  echo "When wrk has finished, paste its complete output here (reading stops at the WRK_SUMMARY line):"
  local line
  : > "${out_file}"
  while IFS= read -r line; do
    printf '%s\n' "${line}" >> "${out_file}"
    [[ "${line}" == *WRK_SUMMARY* ]] && return 0
  done
  return 1
}

wrk_failed() {
  echo "wrk failed or no WRK_SUMMARY line was received; last lines of $1:" >&2
  tail -n 5 "$1" >&2
  exit 1
}

warm_up() {
  local path="$1" url="$2" out_file="${OUT_DIR}/warmup-$1.txt"
  echo "--- WordPress warm-up (${path}, discarded from metrics) ---"
  run_wrk "warmup-${path}" "${url}" "${out_file}" "" "${WARMUP_DURATION}" "warmup-${TARGET_VHOST}" \
    || wrk_failed "${out_file}"
  if [[ "${LOAD_MODE}" == local ]] && ! grep -q 'WRK_SUMMARY ' "${out_file}"; then
    wrk_failed "${out_file}"
  fi
}

# ── Run 1: through WAF ─────────────────────────────────────────────────────
if [[ "${LOAD_TARGET}" == wordpress ]]; then
  warm_up waf "${WAF_URL}"
fi

echo "--- Run 1: through HAProxy+Coraza ---"
run_wrk wrk-waf "${WAF_URL}" "${OUT_DIR}/waf.txt" sample || wrk_failed "${OUT_DIR}/waf.txt"

wait "${SAMPLER_CORAZA_PID:-}" 2>/dev/null || true
wait "${SAMPLER_HAPROXY_PID:-}" 2>/dev/null || true
echo "WAF run complete. Output: ${OUT_DIR}/waf.txt"
copy_audit_log_snapshot "${OUT_DIR}"

# ── Run 2: direct (WAF bypassed) ───────────────────────────────────────────
if [[ "${LOAD_TARGET}" == wordpress ]]; then
  warm_up direct "${DIRECT_URL}"
fi

echo "--- Run 2: direct to ${DIRECT_URL} ---"
run_wrk wrk-direct "${DIRECT_URL}" "${OUT_DIR}/direct.txt" || wrk_failed "${OUT_DIR}/direct.txt"
echo "Direct run complete. Output: ${OUT_DIR}/direct.txt"

if ! grep -q 'WRK_SUMMARY ' "${OUT_DIR}/waf.txt" || ! grep -q 'WRK_SUMMARY ' "${OUT_DIR}/direct.txt"; then
  echo "wrk produced no parseable summary; see waf.txt / direct.txt." >&2
  exit 1
fi

# ── Parse & compute overhead ───────────────────────────────────────────────

echo "Parsing results..."

# Exported rather than interpolated: the heredoc is quoted ('PY') so its regex
# backslashes stay intact, which also means shell variables are not expanded.
export OUT_DIR THREADS CONNECTIONS DURATION WARMUP_DURATION WRK_IMAGE WRK_VERSION LOAD_MODE \
  LOAD_TARGET WAF_URL DIRECT_URL

python3 - <<'PY'
import json
import os
import re

OUT_DIR = os.environ["OUT_DIR"]


def parse_wrk(path):
    """Parse the WRK_SUMMARY line printed by benign-mix.lua's done().

    wrk's own histogram has no p95, and latency:percentile() in Lua gives
    exact values instead of bucketed ones.
    """
    if not os.path.exists(path):
        return {}
    m = re.search(
        r"WRK_SUMMARY\s+requests=(\d+)\s+duration_us=(\d+)\s+rps=([\d.]+)\s+"
        r"lat_p50_us=(\d+)\s+lat_p95_us=(\d+)\s+lat_p99_us=(\d+)\s+errors=(\d+)",
        open(path).read(),
    )
    if not m:
        return {}
    return {
        "requests": int(m.group(1)),
        "rps": float(m.group(3)),
        "latency_ms": {
            "p50": round(int(m.group(4)) / 1000, 3),
            "p95": round(int(m.group(5)) / 1000, 3),
            "p99": round(int(m.group(6)) / 1000, 3),
        },
        "errors": int(m.group(7)),
    }


waf = parse_wrk(f"{OUT_DIR}/waf.txt")
direct = parse_wrk(f"{OUT_DIR}/direct.txt")
waf_lat = waf.get("latency_ms", {})
direct_lat = direct.get("latency_ms", {})

rps_deg = None
if waf.get("rps") and direct.get("rps"):
    rps_deg = round((direct["rps"] - waf["rps"]) / direct["rps"] * 100, 2)

performance = {
    "rps": waf.get("rps"),
    "baseline_rps": direct.get("rps"),
    "rps_degradation_pct": rps_deg,
    "latency_ms": waf_lat,
    "baseline_latency_ms": direct_lat,
    "latency_overhead_ms": {
        p: round(waf_lat[p] - direct_lat[p], 3)
        for p in ("p50", "p95", "p99")
        if p in waf_lat and p in direct_lat
    },
    "waf_requests": waf.get("requests"),
    "waf_errors": waf.get("errors"),
    "baseline_requests": direct.get("requests"),
    "baseline_errors": direct.get("errors"),
    # Failures or blocked requests invalidate the latency/RPS comparison.
    "valid": bool(waf and direct) and waf.get("errors") == 0 and direct.get("errors") == 0,
    "config": {
        "threads": int(os.environ["THREADS"]),
        "connections": int(os.environ["CONNECTIONS"]),
        "duration": os.environ["DURATION"],
        "target": os.environ["LOAD_TARGET"],
        "warmup_duration": os.environ["WARMUP_DURATION"] if os.environ["LOAD_TARGET"] == "wordpress" else None,
        "mode": os.environ["LOAD_MODE"],
        # Manual runs use the client's own wrk build, not the pinned image.
        "wrk_image": os.environ["WRK_IMAGE"] if os.environ["LOAD_MODE"] == "local" else None,
        "wrk_version": os.environ["WRK_VERSION"] or None,
        "waf_url": os.environ["WAF_URL"],
        "direct_url": os.environ["DIRECT_URL"],
    },
}

print(json.dumps(performance, indent=2))
with open(f"{OUT_DIR}/performance.json", "w") as f:
    json.dump(performance, f, indent=2)
PY

PERFORMANCE="$(cat "${OUT_DIR}/performance.json")"
RESOURCES_JSON="$(OUT_DIR="${OUT_DIR}" python3 - <<'PY'
import json
import os

def load(name):
    try:
        with open(os.path.join(os.environ["OUT_DIR"], name)) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}

print(json.dumps({"coraza": load("resources-coraza.json"), "haproxy": load("resources-haproxy.json")}))
PY
)"
write_summary "${SCENARIO}" "${TARGET_VHOST}" "{}" "${PERFORMANCE}" "${RESOURCES_JSON}"

echo ""
OUT_DIR="${OUT_DIR}" python3 - <<'PY'
import json
import os

p = json.load(open(os.path.join(os.environ["OUT_DIR"], "performance.json")))
print(f"WAF RPS     : {p.get('rps')}")
print(f"Direct RPS  : {p.get('baseline_rps')}")
print(f"Degradation : {p.get('rps_degradation_pct')}%")
print(f"Latency WAF    p50/p95/p99 [ms]: {p.get('latency_ms')}")
print(f"Latency direct p50/p95/p99 [ms]: {p.get('baseline_latency_ms')}")
if not p.get("valid"):
    print(
        f"WARNING: errors during the run (WAF: {p.get('waf_errors')}, "
        f"direct: {p.get('baseline_errors')}); these numbers are not a valid overhead measurement."
    )
PY
echo "Results → ${OUT_DIR}/"
