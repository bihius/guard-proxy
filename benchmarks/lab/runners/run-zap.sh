#!/usr/bin/env bash
# run-zap.sh — OWASP ZAP baseline scan for false positive measurement.
#
# Runs a ZAP baseline (passive + active) scan against each lab target through
# HAProxy and classifies WAF alerts as FPs (WAF blocked a legitimate scan
# request) vs TPs (WAF blocked a genuine attack found by ZAP).
#
# Output:
#   benchmarks/results/run-<RUN_ID>/zap-<vhost>/zap.json
#   benchmarks/results/run-<RUN_ID>/zap-<vhost>/zap.html
#   benchmarks/results/run-<RUN_ID>/zap-<vhost>/summary.json
#
# Usage:
#   RUN_ID=... bash benchmarks/lab/runners/run-zap.sh
#   RUN_ID=... TARGET_VHOST=wp.local bash benchmarks/lab/runners/run-zap.sh

set -Eeuo pipefail
: "${RUN_ID:=$(date +%Y%m%d-%H%M%S)}"
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

TARGET_VHOST="${TARGET_VHOST:-${LAB_WP_DOMAIN}}"   # default: WordPress (best FPR target)
ZAP_IMAGE="ghcr.io/zaproxy/zaproxy:stable"
ZAP_CONF="${REPO_ROOT}/benchmarks/lab/scenarios/zap/zap-baseline.conf"
ZAP_ALERT_FILTER="${REPO_ROOT}/benchmarks/lab/scenarios/zap/alert-filter.yaml"

# HAProxy listens on port 80 inside gp_internal; ZAP container joins that network.
TARGET_URL="http://haproxy:80"

write_manifest
SCENARIO="zap-${TARGET_VHOST}"
OUT_DIR="$(setup_run_dir "${SCENARIO}")"

echo "=== OWASP ZAP baseline scan ==="
echo "Target vhost : ${TARGET_VHOST} → ${TARGET_URL}"
echo "Output dir   : ${OUT_DIR}"
echo "Image        : ${ZAP_IMAGE}"
echo ""

# ZAP needs a writable /zap/wrk directory for reports.
docker run --rm \
  --network "${DOCKER_NETWORK}" \
  -v "${OUT_DIR}:/zap/wrk:rw" \
  -v "${ZAP_CONF}:/zap/rules.conf:ro" \
  -e "ZAP_HOST_HEADER=${TARGET_VHOST}" \
  "${ZAP_IMAGE}" \
  zap-baseline.py \
    -t "${TARGET_URL}" \
    -c /zap/rules.conf \
    -J zap.json \
    -r zap.html \
    -I \
    --hook /zap/wrk/zap-hook.py 2>/dev/null \
  || true

# If no hook file exists, run without it.
if [[ ! -f "${OUT_DIR}/zap.json" ]]; then
  docker run --rm \
    --network "${DOCKER_NETWORK}" \
    -v "${OUT_DIR}:/zap/wrk:rw" \
    -v "${ZAP_CONF}:/zap/rules.conf:ro" \
    -e "ZAP_HOST_HEADER=${TARGET_VHOST}" \
    "${ZAP_IMAGE}" \
    zap-baseline.py \
      -t "${TARGET_URL}" \
      -c /zap/rules.conf \
      -J zap.json \
      -r zap.html \
      -I \
  || true
fi

echo "ZAP scan complete. Parsing results..."

# Parse ZAP JSON output and compute a detection summary.
# ZAP alerts with risk >= Medium against the WAF-proxied target are WAF-visible
# attacks. The WAF's job on ZAP traffic:
#   - Block high-risk attacks (SQLi, XSS, ...) → TP if blocked, FN if passed
#   - Allow legitimate ZAP probes (header checks, info gathering) → TN if allowed, FP if blocked

python3 - <<'PY'
import json, sys, os

out_dir = os.environ.get("OUT_DIR", ".")
zap_json = os.path.join(out_dir, "zap.json")

if not os.path.exists(zap_json):
    print(json.dumps({"error": "zap.json not found — scan may have failed or produced no output"}))
    sys.exit(0)

with open(zap_json) as f:
    report = json.load(f)

# ZAP JSON structure: {"site": [{"alerts": [{"riskcode":"3","alert":"SQL Injection",...}]}]}
alerts = []
for site in report.get("site", []):
    alerts.extend(site.get("alerts", []))

# Classify alerts: risk 2 (Medium) or 3 (High) are WAF-relevant attack signals.
# Risk 0 (Informational) / 1 (Low) are cosmetic — not WAF signals.
ATTACK_RISKS = {2, 3}  # Medium, High
attack_alerts = [a for a in alerts if int(a.get("riskcode", 0)) in ATTACK_RISKS]
info_alerts   = [a for a in alerts if int(a.get("riskcode", 0)) not in ATTACK_RISKS]

total_attack_instances = sum(int(a.get("count", 1)) for a in attack_alerts)
total_info_instances   = sum(int(a.get("count", 1)) for a in info_alerts)

# We cannot directly observe WAF blocks from ZAP output alone (ZAP sees the
# app's response, not the WAF block). A separate audit-log cross-reference is
# done in collect-metrics.sh. Here we report ZAP findings as-is.
detection = {
    "total_alerts": len(alerts),
    "attack_severity_alerts": len(attack_alerts),
    "info_severity_alerts": len(info_alerts),
    "attack_instances": total_attack_instances,
    "info_instances": total_info_instances,
    "top_alerts": [
        {"risk": a.get("riskdesc"), "name": a.get("alert"), "count": a.get("count")}
        for a in sorted(attack_alerts, key=lambda x: -int(x.get("riskcode", 0)))[:10]
    ],
    "note": "TP/FP counts require audit-log cross-reference — run collect-metrics.sh after all scenarios."
}

print(json.dumps(detection, indent=2))

with open(os.path.join(out_dir, "detection.json"), "w") as f:
    json.dump(detection, f, indent=2)
PY

export OUT_DIR
DETECTION="$(cat "${OUT_DIR}/detection.json")"
POLICY_NAME="$(env_value LAB_POLICY_NAME 'Lab Baseline')"

write_summary "${SCENARIO}" "${TARGET_VHOST}" "${POLICY_NAME}" "${DETECTION}" "{}" "{}"

echo ""
echo "ZAP alerts: $(python3 -c "import json; d=json.load(open('${OUT_DIR}/detection.json')); print(d.get('total_alerts', 'n/a'))")"
echo "Results → ${OUT_DIR}/"
