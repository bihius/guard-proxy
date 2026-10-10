#!/usr/bin/env bash
# run-load.sh — Test 3: latency and RPS overhead of the WAF (WAF vs direct).
#
# Runs the same wrk workload twice against Albedo (ftw.local):
#   1. Through HAProxy+Coraza  (production path)
#   2. Directly against the Albedo container (WAF bypassed)
#
# Albedo answers every request with 200 and does no work of its own, so the
# difference between the two runs is the cost of HAProxy+Coraza, not of the
# application. The workload is benign and every request in it returns 200
# directly, so any non-2xx response through the WAF is a false positive and
# makes that run invalid (fast 403s would inflate RPS).
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
#   RUN_ID=... TARGET_VHOST=ftw.local DIRECT_HOST=ftw-backend DIRECT_PORT=8080 \
#     bash benchmarks/lab/runners/run-load.sh

set -Eeuo pipefail
: "${RUN_ID:=$(date +%Y%m%d-%H%M%S)}"
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

TARGET_VHOST="${TARGET_VHOST:-${LAB_FTW_DOMAIN}}"
resolve_policy
DIRECT_HOST="${DIRECT_HOST:-ftw-backend}"   # Docker service name for direct access
DIRECT_PORT="${DIRECT_PORT:-8080}"          # Target port (no HAProxy)
# elswork/wrk ships native amd64+arm64 builds of wrk 4.2.0 (williamyeh/wrk is
# amd64-only and segfaults under emulation on Apple Silicon). Pinned by digest
# so re-runs use the same binary; the digest is recorded in performance.json.
WRK_IMAGE="elswork/wrk@sha256:529f8fe35924e549cc270d4128406d5863043e756c31395afd08acccc74ada79"
LUA_SCRIPT="${REPO_ROOT}/benchmarks/lab/scenarios/load/benign-mix.lua"

THREADS="${LOAD_THREADS:-2}"
CONNECTIONS="${LOAD_CONNECTIONS:-20}"
DURATION="${LOAD_DURATION:-30s}"

write_manifest
SCENARIO="load-${TARGET_VHOST}"
OUT_DIR="$(setup_run_dir "${SCENARIO}")"

echo "=== Load test: WAF vs direct ==="
echo "Target vhost : ${TARGET_VHOST}"
echo "Direct host  : ${DIRECT_HOST}:${DIRECT_PORT}"
echo "Load         : ${THREADS} threads, ${CONNECTIONS} connections, ${DURATION}"
echo "Output dir   : ${OUT_DIR}"
echo ""

run_wrk() {
  local case_id="$1" url="$2" out_file="$3"
  docker run --rm --cpuset-cpus="${ATTACKER_CPUSET}" \
    --network "${DOCKER_NETWORK}" \
    -v "${LUA_SCRIPT}:/benign-mix.lua:ro" \
    -e "LOAD_VHOST=${TARGET_VHOST}" \
    -e "EVAL_RUN_ID=${RUN_ID}" \
    -e "EVAL_SCENARIO=${SCENARIO}" \
    -e "EVAL_CASE=${case_id}" \
    "${WRK_IMAGE}" \
    -t "${THREADS}" -c "${CONNECTIONS}" -d "${DURATION}" \
    -s /benign-mix.lua \
    --latency \
    "${url}" \
    > "${out_file}" 2>&1
}

# ── Run 1: through WAF ─────────────────────────────────────────────────────

echo "--- Run 1: through HAProxy+Coraza ---"

CORAZA_CONTAINER="$(compose_container_id coraza)"
HAPROXY_CONTAINER="$(compose_container_id haproxy)"
DURATION_S="${DURATION%s}"

if [[ -n "${CORAZA_CONTAINER}" ]]; then
  sample_container_resources "${CORAZA_CONTAINER}" "${DURATION_S}" "${OUT_DIR}/resources-coraza.json" &
  SAMPLER_CORAZA_PID=$!
fi
if [[ -n "${HAPROXY_CONTAINER}" ]]; then
  sample_container_resources "${HAPROXY_CONTAINER}" "${DURATION_S}" "${OUT_DIR}/resources-haproxy.json" &
  SAMPLER_HAPROXY_PID=$!
fi

run_wrk wrk-waf "http://haproxy:80/" "${OUT_DIR}/waf.txt"

wait "${SAMPLER_CORAZA_PID:-}" 2>/dev/null || true
wait "${SAMPLER_HAPROXY_PID:-}" 2>/dev/null || true
echo "WAF run complete. Output: ${OUT_DIR}/waf.txt"
copy_audit_log_snapshot "${OUT_DIR}"

# ── Run 2: direct (WAF bypassed) ───────────────────────────────────────────

echo "--- Run 2: direct to ${DIRECT_HOST}:${DIRECT_PORT} ---"
run_wrk wrk-direct "http://${DIRECT_HOST}:${DIRECT_PORT}/" "${OUT_DIR}/direct.txt"
echo "Direct run complete. Output: ${OUT_DIR}/direct.txt"

# ── Parse & compute overhead ───────────────────────────────────────────────

echo "Parsing results..."

# Exported rather than interpolated: the heredoc is quoted ('PY') so its regex
# backslashes stay intact, which also means shell variables are not expanded.
export OUT_DIR THREADS CONNECTIONS DURATION WRK_IMAGE

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
    # Albedo answers 200 to every request in the mix: errors on either path
    # mean the run measured failures (or WAF blocks), not overhead.
    "valid": bool(waf and direct) and waf.get("errors") == 0 and direct.get("errors") == 0,
    "config": {
        "threads": int(os.environ["THREADS"]),
        "connections": int(os.environ["CONNECTIONS"]),
        "duration": os.environ["DURATION"],
        "wrk_image": os.environ["WRK_IMAGE"],
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
