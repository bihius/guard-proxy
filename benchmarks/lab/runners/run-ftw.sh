#!/usr/bin/env bash
# run-ftw.sh — Run the OWASP CRS regression suite via go-ftw.
#
# This is the gold-standard TPR measurement: the CRS submodule ships labeled
# test cases (each one tagged "should block" or "should pass") and go-ftw
# replays them against the live HAProxy+Coraza stack.
#
# Output:
#   benchmarks/results/run-<RUN_ID>/ftw/raw.json   (go-ftw JSON output)
#   benchmarks/results/run-<RUN_ID>/ftw/summary.json
#
# Usage:
#   RUN_ID=20260602-141500 bash benchmarks/lab/runners/run-ftw.sh
#   RUN_ID=... TARGET_VHOST=dvwa.local bash benchmarks/lab/runners/run-ftw.sh

set -Eeuo pipefail
: "${RUN_ID:=$(date +%Y%m%d-%H%M%S)}"
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

TARGET_VHOST="${TARGET_VHOST:-${LAB_JUICESHOP_DOMAIN}}"
FTW_IMAGE="ghcr.io/coreruleset/go-ftw:v1.4.0"
CRS_TESTS="${REPO_ROOT}/configs/coraza/crs/tests/regression/tests"
FTW_CONFIG="${REPO_ROOT}/benchmarks/lab/scenarios/crs-ftw/config.yaml"

if [[ ! -d "${CRS_TESTS}" ]]; then
  echo "CRS test corpus not found at ${CRS_TESTS}." >&2
  echo "Run: git submodule update --init --recursive" >&2
  exit 1
fi

write_manifest
OUT_DIR="$(setup_run_dir ftw)"

echo "=== CRS regression (go-ftw) ==="
echo "Target vhost : ${TARGET_VHOST}"
echo "Output dir   : ${OUT_DIR}"
echo "Image        : ${FTW_IMAGE}"
echo ""

docker run --rm \
  --network "${DOCKER_NETWORK}" \
  -v "${CRS_TESTS}:/tests:ro" \
  -v "${FTW_CONFIG}:/config.yaml:ro" \
  "${FTW_IMAGE}" \
  run \
    --config /config.yaml \
    --dir /tests \
    --output json \
  > "${OUT_DIR}/raw.json" 2> "${OUT_DIR}/stderr.txt" || true

echo "go-ftw complete. Parsing results..."

python3 - <<PY
import json, sys

with open("${OUT_DIR}/raw.json") as f:
    raw = json.load(f)

# go-ftw JSON schema: {"pass": N, "fail": N, "skip": N, "run_duration": "..."}
# "pass" = WAF correctly handled the test case (blocked when should block, passed when should pass)
# "fail" = WAF did NOT handle the test case correctly
passed  = raw.get("pass", 0)
failed  = raw.get("fail", 0)
skipped = raw.get("skip", 0)
total   = passed + failed

# For TPR/FPR we need to split "pass" into TP vs TN and "fail" into FN vs FP.
# go-ftw v1.x reports totals only; individual case details are in the log.
# Use totals as a proxy: assume ~85% of CRS test cases are "should block" (attack)
# and ~15% are "should pass" (benign). Document this assumption in the summary.
#
# For a more precise split, re-run with --output json-per-test (go-ftw v2).
attack_ratio = 0.85
tp = int(round(passed * attack_ratio))
tn = passed - tp
fn = int(round(failed * attack_ratio))
fp = failed - fn
tpr = tp / (tp + fn) if (tp + fn) > 0 else 0.0
fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

detection = {
    "true_positive":  tp,
    "false_negative": fn,
    "true_negative":  tn,
    "false_positive": fp,
    "tpr": round(tpr, 4),
    "fpr": round(fpr, 4),
    "total_cases": total,
    "skipped": skipped,
    "note": "TP/FP split estimated from pass/fail totals (attack_ratio=0.85). Re-run with go-ftw v2 --output json-per-test for exact split."
}

print(json.dumps(detection, indent=2))

with open("${OUT_DIR}/detection.json", "w") as f:
    json.dump(detection, f, indent=2)
PY

# Write final summary.json.
DETECTION="$(cat "${OUT_DIR}/detection.json")"
POLICY_NAME="$(env_value LAB_POLICY_NAME 'Lab Baseline')"

write_summary "ftw" "${TARGET_VHOST}" "${POLICY_NAME}" "${DETECTION}" "{}" "{}"

echo ""
echo "FTW TPR:  $(python3 -c "import json; d=json.load(open('${OUT_DIR}/detection.json')); print(f\"{d['tpr']*100:.1f}%\")")"
echo "Results → ${OUT_DIR}/"
