#!/usr/bin/env bash
# run-ftw.sh — Run the OWASP CRS regression suite via go-ftw.
#
# This is the CRS regression/conformance measurement: the CRS submodule ships
# labeled test cases and go-ftw replays them against the live HAProxy+Coraza
# stack.
#
# Output:
#   benchmarks/results/run-<RUN_ID>/ftw/raw.json   (go-ftw JSON output)
#   benchmarks/results/run-<RUN_ID>/ftw/summary.json
#
# Usage:
#   RUN_ID=20260602-141500 bash benchmarks/lab/runners/run-ftw.sh
#   RUN_ID=... TARGET_VHOST=ftw.local bash benchmarks/lab/runners/run-ftw.sh

set -Eeuo pipefail
: "${RUN_ID:=$(date +%Y%m%d-%H%M%S)}"
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

TARGET_VHOST="${TARGET_VHOST:-${LAB_FTW_DOMAIN}}"
FTW_IMAGE="ghcr.io/coreruleset/go-ftw:latest"
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

docker run --rm --cpuset-cpus="${ATTACKER_CPUSET}" \
  --network "${DOCKER_NETWORK}" \
  -v "${CRS_TESTS}:/tests:ro" \
  -v "${FTW_CONFIG}:/config.yaml:ro" \
  -e "TARGET_VHOST=${TARGET_VHOST}" \
  -e "RUN_ID=${RUN_ID}" \
  "${FTW_IMAGE}" \
  run \
    --config /config.yaml \
    --dir /tests \
    -o json \
  > "${OUT_DIR}/raw.json" 2> "${OUT_DIR}/stderr.txt" || true

echo "go-ftw complete. Parsing results..."

copy_audit_log_snapshot "${OUT_DIR}"

PYTHONPATH="${SCRIPT_DIR}" CRS_TESTS="${CRS_TESTS}" OUT_DIR="${OUT_DIR}" python3 - <<'PY'
import json
import os

from eval_metrics import classify_ftw_tests, summarize_ftw

with open(os.path.join(os.environ["OUT_DIR"], "raw.json")) as f:
    raw = json.load(f)

classifications = classify_ftw_tests(os.environ["CRS_TESTS"])
detection = summarize_ftw(raw, classifications)

print(json.dumps(detection, indent=2))

with open(os.path.join(os.environ["OUT_DIR"], "detection.json"), "w") as f:
    json.dump(detection, f, indent=2)
PY

# Write final summary.json.
DETECTION="$(cat "${OUT_DIR}/detection.json")"
resolve_policy

write_summary "ftw" "${TARGET_VHOST}" "${POLICY_NAME}" "${DETECTION}" "{}" "{}" "${POLICY_PARANOIA}"

echo ""
echo "FTW conformance: $(python3 -c "import json; d=json.load(open('${OUT_DIR}/detection.json')); print(f\"{(d.get('crs_conformance_rate') or 0)*100:.1f}%\")")"
echo "Results → ${OUT_DIR}/"
