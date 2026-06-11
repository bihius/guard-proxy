#!/usr/bin/env bash
# run-zap.sh — OWASP ZAP baseline scan for scanner-assisted coverage.
#
# Runs a ZAP baseline scan through HAProxy. ZAP is supplemental evidence, not a
# clean false-positive-rate source, because its traffic mixes crawler requests,
# passive checks, and attack-like probes.
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

TARGET_VHOST="${TARGET_VHOST:-${LAB_WP_DOMAIN}}"   # default: WordPress scanner target
ZAP_IMAGE="ghcr.io/zaproxy/zaproxy:stable"
ZAP_CONF="${REPO_ROOT}/benchmarks/lab/scenarios/zap/zap-baseline.conf"

# HAProxy listens on port 80 inside gp_internal; ZAP container joins that network.
TARGET_URL="http://haproxy:80"

write_manifest
SCENARIO="zap-${TARGET_VHOST}"
OUT_DIR="$(setup_run_dir "${SCENARIO}")"
export OUT_DIR   # must be set before the Python heredoc reads os.environ

echo "=== OWASP ZAP baseline scan ==="
echo "Target vhost : ${TARGET_VHOST} → ${TARGET_URL}"
echo "Output dir   : ${OUT_DIR}"
echo "Image        : ${ZAP_IMAGE}"
echo ""

# ZAP needs a writable /zap/wrk directory for reports.
# The Host: header is injected via ZAP's built-in HTTP Request Header Replacer
# so that every request ZAP sends to haproxy:80 carries the correct vhost name
# and benchmark correlation tags.
# NOTE: zap-baseline.py does NOT accept top-level "-config key=value" args — its
# argument parser treats any "-c..." flag as "-c" (config_file), so "-config"
# gets parsed as "-c" with value "onfig", causing a FileNotFoundError. ZAP-side
# -config overrides must instead be passed bundled inside a single -z argument,
# per `-z zap_options` ("-z \"-config aaa=bbb -config ccc=ddd\"").
ZAP_CONFIG_OPTS="-config replacer.full_list(0).description=host-header \
-config replacer.full_list(0).enabled=true \
-config replacer.full_list(0).matchtype=REQ_HEADER \
-config replacer.full_list(0).matchstr=Host \
-config replacer.full_list(0).replacement=${TARGET_VHOST} \
-config replacer.full_list(0).initiators= \
-config replacer.full_list(1).description=eval-run \
-config replacer.full_list(1).enabled=true \
-config replacer.full_list(1).matchtype=REQ_HEADER \
-config replacer.full_list(1).matchstr=X-GP-Eval-Run \
-config replacer.full_list(1).replacement=${RUN_ID} \
-config replacer.full_list(1).initiators= \
-config replacer.full_list(2).description=eval-scenario \
-config replacer.full_list(2).enabled=true \
-config replacer.full_list(2).matchtype=REQ_HEADER \
-config replacer.full_list(2).matchstr=X-GP-Eval-Scenario \
-config replacer.full_list(2).replacement=${SCENARIO} \
-config replacer.full_list(2).initiators= \
-config replacer.full_list(3).description=eval-case \
-config replacer.full_list(3).enabled=true \
-config replacer.full_list(3).matchtype=REQ_HEADER \
-config replacer.full_list(3).matchstr=X-GP-Eval-Case \
-config replacer.full_list(3).replacement=zap \
-config replacer.full_list(3).initiators="

docker run --rm --cpuset-cpus="21-23" \
  --network "${DOCKER_NETWORK}" \
  -v "${OUT_DIR}:/zap/wrk:rw" \
  -v "${ZAP_CONF}:/zap/rules.conf:ro" \
  "${ZAP_IMAGE}" \
  zap-baseline.py \
    -t "${TARGET_URL}" \
    -c /zap/rules.conf \
    -J zap.json \
    -r zap.html \
    -I \
    -z "${ZAP_CONFIG_OPTS}" \
  > "${OUT_DIR}/zap-stdout.txt" 2>&1 || true

echo "ZAP scan complete. Parsing results..."
copy_audit_log_snapshot "${OUT_DIR}"

# Parse ZAP JSON output and compute a scanner summary. Do not derive FPR/TPR
# from ZAP; the labeled corpus runner is the clean source for those formulas.

python3 - <<'PY'
import json, sys, os

out_dir = os.environ.get("OUT_DIR", ".")
zap_json = os.path.join(out_dir, "zap.json")

if not os.path.exists(zap_json):
    detection = {"error": "zap.json not found — scan may have failed or produced no output"}
    print(json.dumps(detection))
    with open(os.path.join(out_dir, "detection.json"), "w") as f:
        json.dump(detection, f, indent=2)
    sys.exit(0)

with open(zap_json) as f:
    report = json.load(f)

# ZAP JSON structure: {"site": [{"alerts": [{"riskcode":"3","alert":"SQL Injection",...}]}]}
alerts = []
for site in report.get("site", []):
    alerts.extend(site.get("alerts", []))

# Classify alerts: risk 2 (Medium) or 3 (High) are WAF-relevant scanner signals.
# Risk 0 (Informational) / 1 (Low) are retained as context only.
ATTACK_RISKS = {2, 3}  # Medium, High
attack_alerts = [a for a in alerts if int(a.get("riskcode", 0)) in ATTACK_RISKS]
info_alerts   = [a for a in alerts if int(a.get("riskcode", 0)) not in ATTACK_RISKS]

total_attack_instances = sum(int(a.get("count", 1)) for a in attack_alerts)
total_info_instances   = sum(int(a.get("count", 1)) for a in info_alerts)

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
    "note": "Supplemental scanner evidence only. Do not derive FPR/TPR from ZAP; use the tagged corpus runner for labeled FP/FN counts."
}

print(json.dumps(detection, indent=2))

with open(os.path.join(out_dir, "detection.json"), "w") as f:
    json.dump(detection, f, indent=2)
PY

DETECTION="$(cat "${OUT_DIR}/detection.json")"
resolve_policy

write_summary "${SCENARIO}" "${TARGET_VHOST}" "${POLICY_NAME}" "${DETECTION}" "{}" "{}" "${POLICY_PARANOIA}"

echo ""
echo "ZAP alerts: $(python3 -c "import json; d=json.load(open('${OUT_DIR}/detection.json')); print(d.get('total_alerts', 'n/a'))")"
echo "Results → ${OUT_DIR}/"
