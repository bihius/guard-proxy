#!/usr/bin/env bash
# run-load.sh — Latency and RPS measurement (WAF vs direct).
#
# Runs wrk twice against each target:
#   1. Through HAProxy+Coraza  (production path)
#   2. Directly against the target container (bypass WAF)
#
# The delta is the WAF overhead: latency (p50/p95/p99) and RPS degradation %.
#
# Simultaneously samples coraza + haproxy container resource usage.
#
# Output:
#   benchmarks/results/run-<RUN_ID>/load-<vhost>/waf.txt
#   benchmarks/results/run-<RUN_ID>/load-<vhost>/direct.txt
#   benchmarks/results/run-<RUN_ID>/load-<vhost>/resources-coraza.json
#   benchmarks/results/run-<RUN_ID>/load-<vhost>/resources-haproxy.json
#   benchmarks/results/run-<RUN_ID>/load-<vhost>/summary.json
#
# Usage:
#   RUN_ID=... bash benchmarks/lab/runners/run-load.sh
#   RUN_ID=... TARGET_VHOST=juice.local DIRECT_HOST=juiceshop DIRECT_PORT=3000 \
#     bash benchmarks/lab/runners/run-load.sh

set -Eeuo pipefail
: "${RUN_ID:=$(date +%Y%m%d-%H%M%S)}"
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

TARGET_VHOST="${TARGET_VHOST:-${LAB_JUICESHOP_DOMAIN}}"
DIRECT_HOST="${DIRECT_HOST:-juiceshop}"    # Docker service name for direct access
DIRECT_PORT="${DIRECT_PORT:-3000}"         # Target app port (no HAProxy)
# NOTE: ghcr.io/williamyeh/wrk:4.2.0 is not pullable (registry denies access).
# williamyeh/wrk (Docker Hub, no ghcr.io prefix, "latest" tag) is the same
# wrk 4.2.0 build and is publicly pullable.
WRK_IMAGE="williamyeh/wrk:latest"
LUA_SCRIPT="${REPO_ROOT}/benchmarks/lab/scenarios/load/benign-mix.lua"

THREADS="${LOAD_THREADS:-4}"
CONNECTIONS="${LOAD_CONNECTIONS:-50}"
DURATION="${LOAD_DURATION:-60s}"

write_manifest
SCENARIO="load-${TARGET_VHOST}"
OUT_DIR="$(setup_run_dir "${SCENARIO}")"

echo "=== Load test: WAF vs direct ==="
echo "Target vhost : ${TARGET_VHOST}"
echo "Direct host  : ${DIRECT_HOST}:${DIRECT_PORT}"
echo "Load         : ${THREADS} threads, ${CONNECTIONS} connections, ${DURATION}"
echo "Output dir   : ${OUT_DIR}"
echo ""

# ── Through WAF ────────────────────────────────────────────────────────────

echo "--- Run 1: through HAProxy+Coraza ---"

# Start resource sampling in the background during this run.
CORAZA_CONTAINER="$(docker ps --filter "name=coraza" --format "{{.Names}}" | head -1 || true)"
HAPROXY_CONTAINER="$(docker ps --filter "name=haproxy" --format "{{.Names}}" | head -1 || true)"

# Convert duration string to seconds for sampler.
DURATION_S="$(echo "${DURATION}" | sed 's/s$//')"

if [[ -n "${CORAZA_CONTAINER}" ]]; then
  sample_container_resources "${CORAZA_CONTAINER}" "${DURATION_S}" "${OUT_DIR}/resources-coraza.json" &
  SAMPLER_CORAZA_PID=$!
fi
if [[ -n "${HAPROXY_CONTAINER}" ]]; then
  sample_container_resources "${HAPROXY_CONTAINER}" "${DURATION_S}" "${OUT_DIR}/resources-haproxy.json" &
  SAMPLER_HAPROXY_PID=$!
fi

docker run --rm --cpuset-cpus="21-23" \
  --network "${DOCKER_NETWORK}" \
  -v "${LUA_SCRIPT}:/benign-mix.lua:ro" \
  -e "LOAD_VHOST=${TARGET_VHOST}" \
  -e "EVAL_RUN_ID=${RUN_ID}" \
  -e "EVAL_SCENARIO=${SCENARIO}" \
  -e "EVAL_CASE=wrk-waf" \
  "${WRK_IMAGE}" \
  -t "${THREADS}" -c "${CONNECTIONS}" -d "${DURATION}" \
  -s /benign-mix.lua \
  --latency \
  "http://haproxy:80/" \
  > "${OUT_DIR}/waf.txt" 2>&1

# Wait for samplers to finish.
wait "${SAMPLER_CORAZA_PID:-}" 2>/dev/null || true
wait "${SAMPLER_HAPROXY_PID:-}" 2>/dev/null || true

echo "WAF run complete. Output: ${OUT_DIR}/waf.txt"
copy_audit_log_snapshot "${OUT_DIR}"

# ── Direct (bypass WAF) ────────────────────────────────────────────────────

echo "--- Run 2: direct to ${DIRECT_HOST}:${DIRECT_PORT} ---"

docker run --rm --cpuset-cpus="21-23" \
  --network "${DOCKER_NETWORK}" \
  -v "${LUA_SCRIPT}:/benign-mix.lua:ro" \
  -e "LOAD_VHOST=${TARGET_VHOST}" \
  -e "EVAL_RUN_ID=${RUN_ID}" \
  -e "EVAL_SCENARIO=${SCENARIO}" \
  -e "EVAL_CASE=wrk-direct" \
  "${WRK_IMAGE}" \
  -t "${THREADS}" -c "${CONNECTIONS}" -d "${DURATION}" \
  -s /benign-mix.lua \
  --latency \
  "http://${DIRECT_HOST}:${DIRECT_PORT}/" \
  > "${OUT_DIR}/direct.txt" 2>&1

echo "Direct run complete. Output: ${OUT_DIR}/direct.txt"

# ── Parse & compute overhead ───────────────────────────────────────────────

echo "Parsing results..."

python3 - <<'PY'
import re, json, os

def parse_wrk(path):
    """Parse wrk --latency output into a structured dict."""
    if not os.path.exists(path):
        return {}
    text = open(path).read()

    def find_us(pattern):
        m = re.search(pattern, text, re.IGNORECASE)
        if not m: return None
        val, unit = float(m.group(1)), m.group(2).lower()
        multipliers = {"us": 1, "ms": 1000, "s": 1_000_000}
        return val * multipliers.get(unit, 1)

    # Latency percentiles from the --latency histogram section.
    p50  = find_us(r'50%\s+([\d.]+)(\w+)')
    p95  = find_us(r'95%\s+([\d.]+)(\w+)')
    p99  = find_us(r'99%\s+([\d.]+)(\w+)')

    # RPS from the summary line: "Requests/sec: 1234.56"
    rps_m = re.search(r'Requests/sec:\s+([\d.]+)', text)
    rps = float(rps_m.group(1)) if rps_m else None

    return {
        "latency_us": {"p50": p50, "p95": p95, "p99": p99},
        "rps": rps,
        "raw_path": path
    }

waf    = parse_wrk("${OUT_DIR}/waf.txt")
direct = parse_wrk("${OUT_DIR}/direct.txt")

def us_to_ms(us):
    return round(us / 1000, 3) if us is not None else None

def pct_degradation(waf_val, direct_val):
    if waf_val and direct_val and direct_val > 0:
        return round((direct_val - waf_val) / direct_val * 100, 2)
    return None

waf_rps    = waf.get("rps")
direct_rps = direct.get("rps")
rps_deg    = None
if waf_rps and direct_rps and direct_rps > 0:
    rps_deg = round((direct_rps - waf_rps) / direct_rps * 100, 2)

waf_lat    = waf.get("latency_us", {})
direct_lat = direct.get("latency_us", {})

performance = {
    "rps":    waf_rps,
    "baseline_rps": direct_rps,
    "rps_degradation_pct": rps_deg,
    "latency_ms": {
        "p50": us_to_ms(waf_lat.get("p50")),
        "p95": us_to_ms(waf_lat.get("p95")),
        "p99": us_to_ms(waf_lat.get("p99")),
    },
    "latency_overhead_ms": {
        "p50": us_to_ms((waf_lat.get("p50") or 0) - (direct_lat.get("p50") or 0)),
        "p95": us_to_ms((waf_lat.get("p95") or 0) - (direct_lat.get("p95") or 0)),
        "p99": us_to_ms((waf_lat.get("p99") or 0) - (direct_lat.get("p99") or 0)),
    },
    "config": {
        "threads": int("${THREADS}"),
        "connections": int("${CONNECTIONS}"),
        "duration": "${DURATION}"
    }
}

print(json.dumps(performance, indent=2))

with open("${OUT_DIR}/performance.json", "w") as f:
    json.dump(performance, f, indent=2)
PY

PERFORMANCE="$(cat "${OUT_DIR}/performance.json")"
RESOURCES_CORAZA="$(cat "${OUT_DIR}/resources-coraza.json" 2>/dev/null || echo '{}')"
RESOURCES_HAPROXY="$(cat "${OUT_DIR}/resources-haproxy.json" 2>/dev/null || echo '{}')"

RESOURCES_JSON="$(python3 -c "
import json, sys
c = json.loads('''${RESOURCES_CORAZA}''')
h = json.loads('''${RESOURCES_HAPROXY}''')
print(json.dumps({'coraza': c, 'haproxy': h}))
")"
resolve_policy

write_summary "${SCENARIO}" "${TARGET_VHOST}" "${POLICY_NAME}" "{}" "${PERFORMANCE}" "${RESOURCES_JSON}" "${POLICY_PARANOIA}"

echo ""
python3 - <<PY
import json
p = json.load(open("${OUT_DIR}/performance.json"))
rps_waf    = p.get("rps") or 0
rps_direct = p.get("baseline_rps") or 0
rps_deg    = p.get("rps_degradation_pct") or "n/a"
lat        = p.get("latency_ms", {})
print(f"WAF RPS     : {rps_waf:.1f}")
print(f"Direct RPS  : {rps_direct:.1f}")
print(f"Degradation : {rps_deg}%")
print(f"Latency (WAF) p50={lat.get('p50')}ms  p95={lat.get('p95')}ms  p99={lat.get('p99')}ms")
PY
echo "Results → ${OUT_DIR}/"
