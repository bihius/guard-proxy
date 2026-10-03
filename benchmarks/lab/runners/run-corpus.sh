#!/usr/bin/env bash
# run-corpus.sh — Test 1: tagged labeled corpus for TP/FN/TN/FP counts.
#
# Sends known-benign WordPress requests (payloads/legitimate.txt) and
# known-attack payloads (payloads/sqli.txt, xss.txt, lfi.txt) to wp.local
# through HAProxy+Coraza. Every attack payload is sent twice: in a GET query
# parameter and in the body of a POST comment form, so both query-string and
# request-body inspection are covered.
#
# Each request carries stable correlation headers:
#   X-GP-Eval-Run, X-GP-Eval-Scenario, X-GP-Eval-Case
#
# Coraza audit events are matched by those headers. Correctly allowed benign
# requests normally do not appear in the RelevantOnly audit log, so no matching
# blocking event is interpreted as allow.

set -Eeuo pipefail
: "${RUN_ID:=$(date +%Y%m%d-%H%M%S)}"
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

TARGET_VHOST="${TARGET_VHOST:-${LAB_WP_DOMAIN}}"
resolve_policy
SCENARIO="corpus-${TARGET_VHOST}"
OUT_DIR="$(setup_run_dir "${SCENARIO}")"
CASES_JSONL="${OUT_DIR}/cases.jsonl"
AUDIT_LOG="${OUT_DIR}/coraza-audit.log"

BENIGN_FILE="${REPO_ROOT}/benchmarks/payloads/legitimate.txt"
SQLI_FILE="${REPO_ROOT}/benchmarks/payloads/sqli.txt"
XSS_FILE="${REPO_ROOT}/benchmarks/payloads/xss.txt"
LFI_FILE="${REPO_ROOT}/benchmarks/payloads/lfi.txt"

write_manifest
: > "${CASES_JSONL}"

urlencode() {
  python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$1"
}

# send_case <case_id> <expected> <category> <method> <path> [form|json <body>]
send_case() {
  local case_id="$1" expected="$2" category="$3" method="$4" path="$5"
  local body_type="${6:-}" body="${7:-}"
  local -a body_args=()
  case "${body_type}" in
    form) body_args=(-H "Content-Type: application/x-www-form-urlencoded" --data-binary "${body}") ;;
    json) body_args=(-H "Content-Type: application/json" --data-binary "${body}") ;;
  esac

  local status
  status="$(
    docker run --rm --cpuset-cpus="${ATTACKER_CPUSET}" --network "${DOCKER_NETWORK}" curlimages/curl:8.11.1 \
      --silent --show-error --output /dev/null --write-out '%{http_code}' \
      --max-time 10 \
      -X "${method}" \
      -H "Host: ${TARGET_VHOST}" \
      -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64) guard-proxy-eval-corpus/1.0" \
      -H "Accept: text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8" \
      -H "Accept-Language: pl-PL,pl;q=0.9,en;q=0.8" \
      -H "X-GP-Eval-Run: ${RUN_ID}" \
      -H "X-GP-Eval-Scenario: ${SCENARIO}" \
      -H "X-GP-Eval-Case: ${case_id}" \
      ${body_args[@]+"${body_args[@]}"} \
      "http://haproxy:80${path}" 2>/dev/null || true
  )"

  python3 -c '
import json, sys
keys = ("case_id", "expected", "category", "method", "path", "body", "http_status")
print(json.dumps(dict(zip(keys, sys.argv[1:]))))
' "${case_id}" "${expected}" "${category}" "${method}" "${path}" "${body}" "${status}" >> "${CASES_JSONL}"
  printf '  %-10s %-4s %s -> %s\n' "${case_id}" "${method}" "${path}" "${status}"
}

echo "=== Tagged labeled corpus ==="
echo "Target vhost : ${TARGET_VHOST}"
echo "Scenario     : ${SCENARIO}"
echo "Output dir   : ${OUT_DIR}"
echo ""

idx=0
while read -r method path body_type body; do
  [[ -z "${method}" || "${method}" =~ ^# ]] && continue
  idx=$((idx + 1))
  send_case "benign-${idx}" "allow" "benign" "${method}" "${path}" "${body_type}" "${body}"
done < "${BENIGN_FILE}"

for spec in "sqli:${SQLI_FILE}" "xss:${XSS_FILE}" "lfi:${LFI_FILE}"; do
  category="${spec%%:*}"
  file="${spec#*:}"
  idx=0
  while IFS= read -r payload; do
    [[ -z "${payload}" || "${payload}" =~ ^# ]] && continue
    idx=$((idx + 1))
    encoded="$(urlencode "${payload}")"
    send_case "${category}-${idx}-get" "block" "${category}" "GET" "/?s=${encoded}"
    send_case "${category}-${idx}-post" "block" "${category}" "POST" "/wp-comments-post.php" form \
      "comment=${encoded}&author=Eval&email=eval%40example.com&url=&comment_post_ID=1&comment_parent=0&submit=Post+Comment"
  done < "${file}"
done

copy_audit_log_snapshot "${OUT_DIR}" "${AUDIT_LOG}"

PYTHONPATH="${SCRIPT_DIR}" RUN_ID="${RUN_ID}" SCENARIO="${SCENARIO}" \
  CASES_JSONL="${CASES_JSONL}" AUDIT_LOG="${AUDIT_LOG}" OUT_DIR="${OUT_DIR}" python3 - <<'PY'
import json
import os

from eval_metrics import load_json_lines, summarize_tagged_corpus

detection = summarize_tagged_corpus(
    load_json_lines(os.environ["CASES_JSONL"]),
    load_json_lines(os.environ["AUDIT_LOG"]),
    run_id=os.environ["RUN_ID"],
    scenario=os.environ["SCENARIO"],
)
with open(os.path.join(os.environ["OUT_DIR"], "detection.json"), "w") as f:
    json.dump(detection, f, indent=2)
print(
    f"Corpus cases: {detection['total_cases']}  TP={detection['true_positive']} "
    f"FN={detection['false_negative']} TN={detection['true_negative']} FP={detection['false_positive']}"
)
for case in detection["cases"]:
    if case["outcome"] in ("fn", "fp"):
        print(f"  {case['outcome'].upper()}: {case['case_id']} {case['method']} {case['path']} {case.get('body', '')}")
PY

DETECTION="$(cat "${OUT_DIR}/detection.json")"
write_summary "${SCENARIO}" "${TARGET_VHOST}" "${DETECTION}" "{}" "{}"
echo "Results → ${OUT_DIR}/"
