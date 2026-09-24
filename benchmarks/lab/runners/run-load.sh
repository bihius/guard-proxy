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
TARGET_SERVICE="${TARGET_SERVICE:-${DIRECT_HOST}}"  # Compose service restarted before each run
DIRECT_PORT="${DIRECT_PORT:-3000}"         # Target app port (no HAProxy)
# NOTE: ghcr.io/williamyeh/wrk:4.2.0 is not pullable (registry denies access).
# williamyeh/wrk (Docker Hub, no ghcr.io prefix, "latest" tag) is the same
# wrk 4.2.0 build and is publicly pullable.
# williamyeh/wrk is amd64-only and segfaults under emulation on arm64 hosts
# (Apple Silicon); elswork/wrk ships native amd64+arm64 builds of the same tool.
# Pinned by digest (not ":latest") so re-runs always use the same binary and
# results stay comparable across runs; the digest is also recorded in
# performance.json below.
WRK_IMAGE="elswork/wrk@sha256:529f8fe35924e549cc270d4128406d5863043e756c31395afd08acccc74ada79"
LUA_SCRIPT="${REPO_ROOT}/benchmarks/lab/scenarios/load/benign-mix.lua"

# A sustained 50-connection burst was enough to crash the juiceshop target
# (V8 heap exhaustion, see reset_target below), which invalidated the
# WAF-vs-direct comparison rather than measuring it. Lower defaults trade
# some load-test realism for a target that survives the run.
THREADS="${LOAD_THREADS:-2}"
CONNECTIONS="${LOAD_CONNECTIONS:-20}"
DURATION="${LOAD_DURATION:-30s}"

# Juice Shop retains memory on its dynamic routes under sustained load: from a
# fresh start, one 30s run of this mix takes the container from ~150MB to
# ~2.4GB. Near Node's default heap limit (~2GB) it spends seconds per request
# in mark-compact GC and then aborts ("JavaScript heap out of memory";
# restarted by Docker). Whichever run came second therefore measured a
# GC-thrashing or crashing target rather than the WAF. Restarting the target
# before each run gives both runs the same starting state, and the restart
# count shows whether it still crashed mid-run.
TARGET_CONTAINER="$(compose_container_id "${TARGET_SERVICE}")"
if [[ -z "${TARGET_CONTAINER}" ]]; then
  echo "Could not find the ${TARGET_SERVICE} container for compose project ${COMPOSE_PROJECT_NAME:-guard-proxy}." >&2
  exit 1
fi

target_restart_count() {
  docker inspect -f '{{.RestartCount}}' "${TARGET_CONTAINER}"
}

reset_target() {
  echo "Restarting ${TARGET_SERVICE} for a clean starting state..."
  docker restart "${TARGET_CONTAINER}" >/dev/null
  local deadline=$(( SECONDS + 120 ))
  until docker run --rm --network "${DOCKER_NETWORK}" curlimages/curl:8.11.1 \
      --silent --fail --output /dev/null --max-time 5 \
      "http://${DIRECT_HOST}:${DIRECT_PORT}/"; do
    if (( SECONDS >= deadline )); then
      echo "${TARGET_SERVICE} did not become ready within 120s." >&2
      exit 1
    fi
    sleep 2
  done
  # Let startup work (DB seeding, challenge setup) finish before measuring.
  sleep 5
}

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

reset_target
WAF_RESTARTS_BEFORE="$(target_restart_count)"

# Start resource sampling in the background during this run.
CORAZA_CONTAINER="$(compose_container_id coraza)"
HAPROXY_CONTAINER="$(compose_container_id haproxy)"

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

docker run --rm --cpuset-cpus="${ATTACKER_CPUSET}" \
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

WAF_TARGET_RESTARTS=$(( $(target_restart_count) - WAF_RESTARTS_BEFORE ))
# Wait for samplers to finish.
wait "${SAMPLER_CORAZA_PID:-}" 2>/dev/null || true
wait "${SAMPLER_HAPROXY_PID:-}" 2>/dev/null || true

echo "WAF run complete. Output: ${OUT_DIR}/waf.txt"
copy_audit_log_snapshot "${OUT_DIR}"

# ── Direct (bypass WAF) ────────────────────────────────────────────────────

echo "--- Run 2: direct to ${DIRECT_HOST}:${DIRECT_PORT} ---"

reset_target
DIRECT_RESTARTS_BEFORE="$(target_restart_count)"

docker run --rm --cpuset-cpus="${ATTACKER_CPUSET}" \
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

DIRECT_TARGET_RESTARTS=$(( $(target_restart_count) - DIRECT_RESTARTS_BEFORE ))
echo "Direct run complete. Output: ${OUT_DIR}/direct.txt"

# ── Parse & compute overhead ───────────────────────────────────────────────

echo "Parsing results..."

# Exported rather than interpolated into the heredoc below: the heredoc is
# quoted ('PY') so its regex backslashes are not shell-expanded, which means
# shell variables inside it are not substituted either — os.environ is the
# only reliable way to pass values in.
export OUT_DIR THREADS CONNECTIONS DURATION WRK_IMAGE WAF_TARGET_RESTARTS DIRECT_TARGET_RESTARTS

python3 - <<'PY'
import re, json, os

OUT_DIR = os.environ["OUT_DIR"]
THREADS = os.environ["THREADS"]
CONNECTIONS = os.environ["CONNECTIONS"]
DURATION = os.environ["DURATION"]
WRK_IMAGE = os.environ["WRK_IMAGE"]
WAF_TARGET_RESTARTS = int(os.environ["WAF_TARGET_RESTARTS"])
DIRECT_TARGET_RESTARTS = int(os.environ["DIRECT_TARGET_RESTARTS"])

def parse_wrk(path):
    """Parse wrk --latency output into a structured dict.

    Reads the WRK_SUMMARY line emitted by benign-mix.lua's done() callback
    rather than the human-readable histogram: wrk's default histogram only
    prints the 50/75/90/99 percentiles (no 95%), and Lua's
    latency:percentile() gives exact values instead of bucketed ones.
    """
    if not os.path.exists(path):
        return {}
    text = open(path).read()

    m = re.search(
        r'WRK_SUMMARY\s+requests=(\d+)\s+duration_us=(\d+)\s+rps=([\d.]+)\s+'
        r'lat_p50_us=(\d+)\s+lat_p95_us=(\d+)\s+lat_p99_us=(\d+)\s+errors=(\d+)',
        text,
    )
    if not m:
        return {}

    return {
        "latency_us": {"p50": float(m.group(4)), "p95": float(m.group(5)), "p99": float(m.group(6))},
        "rps": float(m.group(3)),
        "requests": int(m.group(1)),
        "errors": int(m.group(7)),
        "raw_path": path
    }

waf    = parse_wrk(f"{OUT_DIR}/waf.txt")
direct = parse_wrk(f"{OUT_DIR}/direct.txt")

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
        "threads": int(THREADS),
        "connections": int(CONNECTIONS),
        "duration": DURATION,
        "wrk_image": WRK_IMAGE
    },
    "waf_requests": waf.get("requests"),
    "waf_errors": waf.get("errors"),
    "baseline_requests": direct.get("requests"),
    "baseline_errors": direct.get("errors"),
    # Non-zero means the target crashed during that run and its numbers
    # describe the crash, not the WAF.
    "waf_target_restarts": WAF_TARGET_RESTARTS,
    "baseline_target_restarts": DIRECT_TARGET_RESTARTS
}

print(json.dumps(performance, indent=2))

with open(f"{OUT_DIR}/performance.json", "w") as f:
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
if p.get("waf_target_restarts") or p.get("baseline_target_restarts"):
    print("WARNING: the target restarted during a run; these numbers are not valid.")
PY
echo "Results → ${OUT_DIR}/"
