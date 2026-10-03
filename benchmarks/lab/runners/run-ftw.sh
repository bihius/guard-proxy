#!/usr/bin/env bash
# run-ftw.sh — Test 2: OWASP CRS regression suite via go-ftw (log mode).
#
# The CRS submodule ships labeled regression tests: each one sends a request
# and lists the rule IDs that must fire (expect_ids) or must stay silent
# (no_expect_ids). go-ftw replays them through HAProxy+Coraza to the ftw.local
# vhost and checks the rule IDs in the Coraza error log. The result answers
# one question: does CRS behave in this integration as the CRS project
# specifies? It is not a detection rate.
#
# Tests that cannot pass here by design are excluded before the run (go-ftw
# "ignore"), and counted separately:
#   - rules above the vhost policy's paranoia level (not loaded),
#   - response rules (Guard Proxy inspects requests only).
#
# Output:
#   benchmarks/results/run-<RUN_ID>/ftw/raw.json          (go-ftw JSON output)
#   benchmarks/results/run-<RUN_ID>/ftw/coraza-ftw.log    (Coraza log of the run)
#   benchmarks/results/run-<RUN_ID>/ftw/detection.json
#   benchmarks/results/run-<RUN_ID>/ftw/summary.json
#
# Usage:
#   RUN_ID=... bash benchmarks/lab/runners/run-ftw.sh
#   RUN_ID=... TARGET_VHOST=ftw.local bash benchmarks/lab/runners/run-ftw.sh

set -Eeuo pipefail
: "${RUN_ID:=$(date +%Y%m%d-%H%M%S)}"
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

TARGET_VHOST="${TARGET_VHOST:-${LAB_FTW_DOMAIN}}"
resolve_policy
FTW_IMAGE="ghcr.io/coreruleset/go-ftw:2.6.0"
CRS_DIR="${REPO_ROOT}/configs/coraza/crs"
CRS_TESTS="${CRS_DIR}/tests/regression/tests"
FTW_CONFIG="${REPO_ROOT}/benchmarks/lab/scenarios/crs-ftw/config.yaml"

if [[ ! -d "${CRS_TESTS}" ]]; then
  echo "CRS test corpus not found at ${CRS_TESTS}." >&2
  echo "Run: git submodule update --init --recursive" >&2
  exit 1
fi

CORAZA_CONTAINER="$(compose_container_id coraza)"
if [[ -z "${CORAZA_CONTAINER}" ]]; then
  echo "coraza container not found. Run \`make lab-up\` first." >&2
  exit 1
fi

write_manifest
OUT_DIR="$(setup_run_dir ftw)"
RENDERED_FTW_CONFIG="${OUT_DIR}/config.yaml"
CORAZA_LOG="${OUT_DIR}/coraza-ftw.log"
CORAZA_AUDIT_VOLUME="${COMPOSE_PROJECT_NAME:-guard-proxy}_coraza_audit"

# Render the config: go-ftw does not expand {{ env }} templates in its config
# file, and the ignore list depends on the policy's paranoia level.
PYTHONPATH="${SCRIPT_DIR}" TARGET_VHOST="${TARGET_VHOST}" RUN_ID="${RUN_ID}" \
  POLICY_JSON="${POLICY_JSON}" CRS_DIR="${CRS_DIR}" CRS_TESTS="${CRS_TESTS}" \
  python3 - "${FTW_CONFIG}" "${RENDERED_FTW_CONFIG}" "${OUT_DIR}/exclusions.json" <<'PY'
import json
import os
import re
import sys

from eval_metrics import classify_ftw_tests, crs_rule_paranoia_levels, ftw_exclusions

source, target, exclusions_path = sys.argv[1:4]
paranoia = int(json.loads(os.environ["POLICY_JSON"])["paranoia"])
exclusions = ftw_exclusions(
    classify_ftw_tests(os.environ["CRS_TESTS"]),
    crs_rule_paranoia_levels(os.path.join(os.environ["CRS_DIR"], "rules")),
    paranoia,
)

text = re.sub(r'\{\{ env "(\w+)" \}\}', lambda m: os.environ[m.group(1)], open(source).read())
lines = [text.rstrip("\n"), "  ignore:"]
lines += [f"    {json.dumps(pattern)}: {json.dumps(reason)}" for pattern, reason in exclusions.items()]
open(target, "w").write("\n".join(lines) + "\n")
json.dump(exclusions, open(exclusions_path, "w"), indent=2)
print(f"PL{paranoia}: {len(exclusions)} rules excluded from the run (see exclusions.json).")
PY

echo "=== CRS regression (go-ftw, log mode) ==="
echo "Target vhost : ${TARGET_VHOST}"
echo "Output dir   : ${OUT_DIR}"
echo "Image        : ${FTW_IMAGE}"
echo ""

# The lab overlay tees Coraza's log (matched rules) into error.log on the
# coraza_audit volume; go-ftw mounts the same volume and reads it directly.
# Remember where the file ends now, to keep only this run's part afterwards.
LOG_START="$(docker exec "${CORAZA_CONTAINER}" sh -c 'stat -c %s /var/log/coraza/error.log 2>/dev/null || echo 0')"

# go-ftw exits non-zero when any test fails; the result is still in raw.json.
docker run --rm --cpuset-cpus="${ATTACKER_CPUSET}" \
  --network "${DOCKER_NETWORK}" \
  -v "${CRS_TESTS}:/tests:ro" \
  -v "${RENDERED_FTW_CONFIG}:/config.yaml:ro" \
  -v "${CORAZA_AUDIT_VOLUME}:/var/log/coraza:ro" \
  "${FTW_IMAGE}" \
  run \
    --config /config.yaml \
    --dir /tests \
    -o json \
  > "${OUT_DIR}/raw.json" 2> "${OUT_DIR}/stderr.txt" || true

docker exec "${CORAZA_CONTAINER}" tail -c "+$((LOG_START + 1))" /var/log/coraza/error.log > "${CORAZA_LOG}"
echo "go-ftw complete. Parsing results..."

copy_audit_log_snapshot "${OUT_DIR}"

PYTHONPATH="${SCRIPT_DIR}" CRS_TESTS="${CRS_TESTS}" OUT_DIR="${OUT_DIR}" python3 - <<'PY'
import json
import os

from eval_metrics import classify_ftw_tests, summarize_ftw

out_dir = os.environ["OUT_DIR"]
with open(os.path.join(out_dir, "raw.json")) as f:
    raw = json.load(f)
with open(os.path.join(out_dir, "exclusions.json")) as f:
    exclusions = json.load(f)

detection = summarize_ftw(raw, classify_ftw_tests(os.environ["CRS_TESTS"]), exclusions)
with open(os.path.join(out_dir, "detection.json"), "w") as f:
    json.dump(detection, f, indent=2)
print(json.dumps({k: v for k, v in detection.items() if k != "failed_ids"}, indent=2))
PY

DETECTION="$(cat "${OUT_DIR}/detection.json")"
write_summary "ftw" "${TARGET_VHOST}" "${DETECTION}" "{}" "{}"

echo ""
echo "Results → ${OUT_DIR}/"
