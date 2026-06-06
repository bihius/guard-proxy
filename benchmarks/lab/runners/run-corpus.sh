#!/usr/bin/env bash
# run-corpus.sh — Tagged labeled corpus for defensible FP/FN counts.
#
# Sends known-benign and known-attack requests with stable correlation headers:
#   X-GP-Eval-Run, X-GP-Eval-Scenario, X-GP-Eval-Case
#
# Coraza audit events are matched by those headers. Correctly allowed benign
# requests normally do not appear in the RelevantOnly audit log, so no matching
# blocking event is interpreted as allow.

set -Eeuo pipefail
: "${RUN_ID:=$(date +%Y%m%d-%H%M%S)}"
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

TARGET_VHOST="${TARGET_VHOST:-${LAB_WP_DOMAIN}}"
SCENARIO="corpus-${TARGET_VHOST}"
OUT_DIR="$(setup_run_dir "${SCENARIO}")"
CASES_JSONL="${OUT_DIR}/cases.jsonl"
RESPONSES_JSONL="${OUT_DIR}/responses.jsonl"
AUDIT_LOG="${OUT_DIR}/coraza-audit.log"

BENIGN_FILE="${REPO_ROOT}/benchmarks/payloads/legitimate.txt"
SQLI_FILE="${REPO_ROOT}/benchmarks/payloads/sqli.txt"
XSS_FILE="${REPO_ROOT}/benchmarks/payloads/xss.txt"
LFI_FILE="${REPO_ROOT}/benchmarks/payloads/lfi.txt"

write_manifest
: > "${CASES_JSONL}"
: > "${RESPONSES_JSONL}"

urlencode() {
  python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$1"
}

record_case() {
  local case_id="$1" expected="$2" category="$3" method="$4" path="$5"
  python3 - <<PY >> "${CASES_JSONL}"
import json
print(json.dumps({
    "case_id": "${case_id}",
    "expected": "${expected}",
    "category": "${category}",
    "method": "${method}",
    "path": "${path}",
}))
PY
}

send_case() {
  local case_id="$1" expected="$2" category="$3" method="$4" path="$5"
  local status
  status="$(
    docker run --rm --network "${DOCKER_NETWORK}" curlimages/curl:8.11.1 \
      --silent --show-error --output /dev/null --write-out '%{http_code}' \
      --max-time 10 \
      -X "${method}" \
      -H "Host: ${TARGET_VHOST}" \
      -H "User-Agent: guard-proxy-eval-corpus/1.0" \
      -H "X-GP-Eval-Run: ${RUN_ID}" \
      -H "X-GP-Eval-Scenario: ${SCENARIO}" \
      -H "X-GP-Eval-Case: ${case_id}" \
      "http://haproxy:80${path}" 2>/dev/null || true
  )"
  record_case "${case_id}" "${expected}" "${category}" "${method}" "${path}"
  python3 - <<PY >> "${RESPONSES_JSONL}"
import json
print(json.dumps({
    "case_id": "${case_id}",
    "http_status": "${status}",
}))
PY
}

echo "=== Tagged labeled corpus ==="
echo "Target vhost : ${TARGET_VHOST}"
echo "Scenario     : ${SCENARIO}"
echo "Output dir   : ${OUT_DIR}"
echo ""

idx=0
while IFS= read -r path; do
  [[ -z "${path}" || "${path}" =~ ^# ]] && continue
  idx=$((idx + 1))
  send_case "benign-${idx}" "allow" "benign" "GET" "${path}"
done < "${BENIGN_FILE}"

for spec in "sqli:${SQLI_FILE}" "xss:${XSS_FILE}" "lfi:${LFI_FILE}"; do
  category="${spec%%:*}"
  file="${spec#*:}"
  idx=0
  while IFS= read -r payload; do
    [[ -z "${payload}" || "${payload}" =~ ^# ]] && continue
    idx=$((idx + 1))
    encoded="$(urlencode "${payload}")"
    send_case "${category}-${idx}" "block" "${category}" "GET" "/?gp_eval_payload=${encoded}"
  done < "${file}"
done

copy_audit_log_snapshot "${OUT_DIR}" "${AUDIT_LOG}"

PYTHONPATH="${SCRIPT_DIR}" RUN_ID="${RUN_ID}" SCENARIO="${SCENARIO}" \
  CASES_JSONL="${CASES_JSONL}" AUDIT_LOG="${AUDIT_LOG}" python3 - <<'PY'
import json
import os

from eval_metrics import load_json_lines, summarize_tagged_corpus

cases = load_json_lines(os.environ["CASES_JSONL"])
events = load_json_lines(os.environ["AUDIT_LOG"])
detection = summarize_tagged_corpus(
    cases,
    events,
    run_id=os.environ["RUN_ID"],
    scenario=os.environ["SCENARIO"],
)
print(json.dumps(detection, indent=2))
with open(os.path.join(os.path.dirname(os.environ["CASES_JSONL"]), "detection.json"), "w") as f:
    json.dump(detection, f, indent=2)
PY

DETECTION="$(cat "${OUT_DIR}/detection.json")"
POLICY_NAME="$(env_value LAB_POLICY_NAME 'Lab Baseline')"
write_summary "${SCENARIO}" "${TARGET_VHOST}" "${POLICY_NAME}" "${DETECTION}" "{}" "{}"

echo ""
python3 - <<PY
import json
d = json.load(open("${OUT_DIR}/detection.json"))
print(f"Corpus cases: {d['total_cases']}  TP={d['true_positive']} FN={d['false_negative']} TN={d['true_negative']} FP={d['false_positive']}")
PY
echo "Results → ${OUT_DIR}/"
